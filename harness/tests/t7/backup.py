"""T7 group: the backup to the iCloud Drive folder (DEBT67, capture photographs exist in one place).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.

THE CONTRACT THE BUILD MEETS. The checks are written first, so every name the build needs is pinned here.
A GOOD COPY IS NEVER REPLACED BY A BAD ONE: no photograph or capture in the destination is ever overwritten,
and no damaged store snapshot is ever moved in.

  scripts/backup-daily.py     the job, modelled on `scripts/price-refresh-daily.py` (DEBT69).
                              No flag: run once, exit 0 for ok and non-zero for failed.
                              `--verify`: read-only, see "the verify run" below.
                              `--agent [--remove]` installs or removes the launchd job (kept, not installed).
                              Module names `LABEL = "com.banchi.backup"`, `ROOT` (the checkout) and
                              `agent(remove)`, which calls `launchagent.agent` (`scripts/launchagent.py`) and
                              reads the module's `ROOT` when it is called, not when it is defined. The job
                              names `launchctl` nowhere else: the shared helper is the only caller.
  make backup                 `scripts/backup-daily.py $(ARGS)`, once, now; `ARGS=--verify` checks the copy.
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
                              waited on. It is built OUTSIDE the destination and only the finished file is
                              moved in, so a killed run leaves no temp or journal file there and a failed run
                              leaves the last good snapshot.
  the integrity check         the finished snapshot must pass `PRAGMA integrity_check` BEFORE anything is moved
                              in (the online backup copies a damaged page without reading it). A store that
                              fails it moves in nothing of any name: the run ends `failed`, the nightly, the
                              weekly and the dated copy stay as the last good run left them, and the
                              photographs are still copied. On a first run it leaves no store copy at all.
  the snapshots               (owner ruling) the destination keeps the nightly, `inventory/store.sqlite`,
                              replaced every run, and the weekly, at the relative path in the job's
                              `WEEKLY_SNAPSHOT` constant (a string; the checks read it from there). The weekly
                              is made on the first night and then replaced only when its file's mtime is 7 days
                              or more old, from that night's good snapshot. A night whose snapshot fails
                              replaces neither. A night that fails only on bad files (see the copy) still
                              has a good snapshot and replaces the nightly; the weekly on such a night is
                              not pinned.
  the dated copy              a third file, at the relative path in the job's `DATED_SNAPSHOT` constant (a
                              string with one `%s`, filled with the local date `YYYY-MM-DD`; the checks read it
                              from there). It is written once per local day and NEVER replaced: a second run the
                              same day keeps the day's first copy, byte for byte, while the nightly moves on.
  the shrink guard            (DEBT67) the job keeps a SIDECAR beside the last-run line: the file named by its
                              `SIDECAR` constant (a plain file name in the machine folder, not the last-run
                              file and not a lock). It holds the `cards` and `boxes` row counts of the last
                              GOOD run (one that ended `ok`) and is written by a good run only. On a night the
                              weekly is due, a store whose `cards` or `boxes` count is MORE THAN HALF below
                              the sidecar's (exactly half is fine) replaces neither snapshot, ends `failed`
                              and leaves the sidecar as it was, so the next night compares to the same good
                              run. The counts come from the sidecar and the night's store (D88), never from a
                              file in the destination. Other nights are not pinned. No sidecar is a first night.
  the copy                   every file under `photos/` and `captures/`. A destination file is NEVER
                              overwritten. One that is missing is copied. One with the source's size and mtime
                              is skipped, decided by `stat` alone: the job never opens a destination file (an
                              evicted iCloud file would download). One that exists with another size or
                              mtime (a re-shoot, D26, looks like this) is left untouched and counted as
                              `differs`: the run ends `failed`, its reason carries that count as `N files differ`
                              and says that accepting one is a manual act (delete its copy by hand), and the
                              walk goes on, so a missing file is still copied. The differs are not forgotten:
                              the next run fails the same way. It never deletes in the destination, so a sold
                              card's photograph (D89) stays.
                              Mtimes within 2 s of each other count as equal (a synced folder rounds them);
                              the size must still match. One file that cannot be read or stat-ed (a dangling
                              link, no permission) does not stop the run: the rest are copied, the snapshot is
                              made, the run ends `failed` and its reason carries the count of such files. A
                              folder under `photos/` that cannot be listed (no permission) counts as one such
                              file: `os.walk` skips it unasked. A source with no `photos/` tree is a failed
                              run, never `ok copied=0`.
  the checkout                a linked worktree (`ROOT/.git` is a file) with the destination variable unset
                              refuses: non-zero, a sentence naming the worktree, nothing written to the
                              default destination. The main tree (`.git` a folder) runs. With the variable
                              SET a linked worktree runs (exit 0 on a good night) but writes neither the
                              last-run line nor the sidecar: `~/.banchi` is shared by every checkout (D43), so
                              a test run there would overwrite the owner's real status. Its machine folder
                              holds nothing but an optional lock afterwards.
  the last-run line           `<machine dir>/backup-last-run` (`~/.banchi/`, `ports.machine_dir`), one line,
                              overwritten each run: `%Y-%m-%dT%H:%M:%S ok copied=N skipped=M` or
                              `%Y-%m-%dT%H:%M:%S failed <reason>`. N and M count the files of `photos/` and
                              `captures/` written and skipped; the snapshot is not counted. A lock file and
                              the sidecar beside it are allowed; nothing else is written there.
  `status_line() -> str`      a module function of the job, which `make status` prints: the last-run line, or
                              a line saying no backup has run. Never empty. An absent last-run file is that
                              plain line and not an error: this job never runs in a worktree or on CI. A line
                              older than 36 hours (by its own time and by the file's mtime) carries the word
                              `stale`; a younger line does not. The checks load the job alone: the status
                              printer is not named here, or the harness scope would widen to what it reads.
  the verify run              `--verify`: read-only. It hashes (sha256) every source file of `photos/` and
                              `captures/` against the destination and runs the integrity check on the newest dated
                              copy. It prints one line with `matches=N mismatches=N missing=N` and `integrity=ok`
                              (or `bad`), then one `mismatch <path>` or `missing <path>` line per bad file, and exits
                              0 only when nothing mismatches, nothing is missing and the copy is `ok`. It reads
                              destination files on purpose, so a flipped byte under an unchanged size and mtime
                              is seen. It writes nothing: not the destination, not the machine folder, no
                              last-run line.

WHAT THE CHECKS DO NOT RUN. `--agent` is never executed: it bootstraps a real launchd job. The agent half is
proved through the module with a fake `launchctl` first on PATH, a fake HOME and a fake checkout root.

EVERY CHECK PAIRS A NEGATIVE WITH A POSITIVE. A missing script exits 2 and touches nothing, which would pass
"exits non-zero", "left the source alone" and "kept the destination file" for a job that does nothing. So each
of those is asserted beside a run that reported ok and copied, or beside the recorded `failed` line.

Temp files: `robust` opens one run folder `<pid>-<uuid>` per check, from the repo's one helper
(`harness/tests/home.py:run_folder`, test-temp-standard), and its exit removes it, read-only paths
included. No `TemporaryDirectory`, no `isolated_home`. The first check proves the helper's delete.
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
import signal
import sqlite3
import subprocess
import sys
import time
import uuid
from collections import namedtuple
from pathlib import Path
from unittest import mock

from harness.tests import Checks
from harness.tests.home import TEMP_ROOT, open_up, remove_tree, run_folder
from harness.tests.t7.common import REPO_ROOT
from store import db, files

SCRIPT = REPO_ROOT / "scripts" / "backup-daily.py"
LABEL = "com.banchi.backup"
NIGHTLY = "inventory/store.sqlite"
DAY = 86400
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


#: The open run folder of the check now running. `robust` sets it and clears it; `Case` reads it.
RUN_FOLDER: Path | None = None


def robust(fn):
    """A check that raises reads as one failed line with its sentence, never as a traceback
    that hides the rest of the group (the build may not exist yet). It also gives the check its
    run folder, removed when the check ends, whatever the check left read-only."""
    @functools.wraps(fn)
    def run(checks: Checks) -> None:
        global RUN_FOLDER
        with run_folder() as RUN_FOLDER:
            try:
                fn(checks)
            except Exception as exc:  # noqa: BLE001
                checks.ok(False, f"{fn.__name__} ran to the end", f"{type(exc).__name__}: {exc}")
            finally:
                RUN_FOLDER = None
    return run


class Case:
    """One case's folders, all inside the run folder: a fake HOME, a source store root, a destination."""

    def __init__(self, name: str):
        self.root = RUN_FOLDER / name
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


def job_constant(name: str):
    """A string constant of the job, read from its source (the allow list points at the constant the
    code emits, never a copy). None when the job or the constant is absent."""
    try:
        tree = ast.parse(SCRIPT.read_text())
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
                and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)):
            return node.value.value
    return None


def dest_env():
    """The destination-override variable, from the job's `DEST_ENV` constant."""
    return job_constant("DEST_ENV")


def weekly_rel():
    """The weekly snapshot's path under the destination, from the job's `WEEKLY_SNAPSHOT` constant, or
    None when the job has none or it is not a plain relative path of its own."""
    rel = job_constant("WEEKLY_SNAPSHOT")
    parts = Path(rel).parts if rel else ()
    plain = parts and not Path(rel).is_absolute() and ".." not in parts and parts[0] not in ("photos", "captures")
    return Path(*parts).as_posix() if plain and Path(*parts).as_posix() != NIGHTLY else None


def run_job(case: Case, dest=DEFAULT, cmd=None, args=()) -> Ran:
    """The job as launchd runs it: a fresh process, a fake HOME, the source and destination named by env.

    HOME is overridden so `~/.banchi` and the default iCloud path land in the run folder even when the
    build ignores the destination override. `dest=None` leaves the destination to its default. `cmd` is
    the argument list after the interpreter, for a copy of the job in a fake checkout or a wrapper. With no
    `cmd` the job runs from a fake main tree, so a run inside a linked worktree still takes the main-tree path;
    `args` are the flags after it (`--verify`).
    """
    name = dest_env()
    if name is None:
        return Ran(None, "", "scripts/backup-daily.py does not define the DEST_ENV constant")
    if cmd is None:
        tree = case.root / "job-tree" / "scripts" / SCRIPT.name
        cmd = [str(tree if tree.exists() else fake_checkout(case, "job-tree", linked=False)), *args]
    env = dict(os.environ)
    env.pop("BANCHI_SLOT_REGISTRY", None)
    env.update(HOME=str(case.home), BANCHI_HOME=str(case.src))
    if dest is None:
        env.pop(name, None)
    else:
        env[name] = str(case.dest if dest is DEFAULT else dest)
    try:
        done = subprocess.run(
            [sys.executable, *cmd], cwd=case.root, env=env, capture_output=True, text=True, timeout=TIMEOUT,
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


def expect_differs(checks: Checks, label: str, ran: Ran, case: Case, count: int) -> bool:
    """The negative the never-overwrite rule hangs on: exit non-zero and a recorded `failed` line that carries
    the count of files left untouched and says that accepting one is a manual act."""
    line = last_run(case) or {}
    raw = line.get("raw") or ""
    named = re.search(rf"\b{count} files? differs?\b", raw) is not None and re.search(r"by hand|manual", raw, re.I) is not None
    ok = ran.code not in (0, None) and line.get("verdict") == "failed" and named
    return checks.ok(ok, label, f"expected {count} differing files named; exit {ran.code}, last-run {raw!r}\n{said(ran)}")


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


def copy_view(snap: Path, scratch: Path):
    """(rows, integrity) of a store file, read from a copy in `scratch` so reading it leaves no `-wal` or
    `-shm` beside the file under test. (None, why) when it cannot be opened."""
    probe = scratch / "store.sqlite"
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


def snapshot_view(case: Case, rel: str = NIGHTLY):
    """(rows, integrity) of a destination snapshot. (None, why) when it is absent or cannot be opened."""
    snap = case.dest / rel
    if not snap.is_file():
        return None, f"no snapshot at {snap}"
    return copy_view(snap, case.root / "verify")


def integrity_ok(case: Case, path: Path) -> bool:
    """Whether a store file passes SQLite's integrity check on its own, read from a copy."""
    return copy_view(path, case.root / "integrity")[1] == [("ok",)]


def make_readonly(root: Path) -> None:
    for folder in [root, *[p for p in root.rglob("*") if p.is_dir()]]:
        folder.chmod(0o500)


def add_row(case: Case, key: str) -> None:
    """Commit one more row to the source store, so a snapshot made after it differs from one made before."""
    conn = db.connect(case.src / "inventory")
    try:
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, "added"))
    finally:
        conn.close()


def store_rows(case: Case) -> dict:
    return committed_rows(case.src / "inventory" / "store.sqlite")


def age(path: Path, days: float) -> None:
    """Make a destination file `days` old by its mtime, the one clock the weekly's age is read from."""
    then = time.time_ns() - int(days * DAY * SECOND)
    os.utime(path, ns=(then, then))


def dated_pattern():
    """A regex for the dated copy's path under the destination (`inventory/store-YYYY-MM-DD.sqlite`), built
    from the job's `DATED_SNAPSHOT` constant. None when the job names none."""
    rel = job_constant("DATED_SNAPSHOT")
    return re.escape(rel).replace("%s", r"\d{4}-\d\d-\d\d") if rel and rel.count("%s") == 1 else None


def dated_copies(case: Case) -> list:
    """The dated copies in the destination, as relative paths, oldest name first."""
    pattern = dated_pattern()
    return sorted(rel for rel in dest_files(case) if pattern and re.fullmatch(pattern, rel))


def strays(case: Case):
    """Destination files that are neither a copied photograph or capture nor a snapshot (the nightly, the weekly
    or a dated copy): a temp, `-wal`, `-shm` or journal file would be one. None when the destination is not there."""
    if not case.dest.is_dir():
        return None
    snapshots = {NIGHTLY, weekly_rel(), *dated_copies(case)}
    return sorted(rel for rel in dest_files(case) if rel not in FILES and rel not in snapshots)


#: The store the shrink checks start from; each drop is measured against it.
SIZE = {"cards": 10, "boxes": 4}


def seed_counts(inventory: Path, cards: int, boxes: int, pad: int = 0) -> None:
    """Make the store hold exactly this many `cards` and `boxes` rows (the real schema, D88), committed.
    `pad` makes each payload that many bytes longer, so the file spans enough pages to damage one."""
    payload = '{"x": "%s"}' % ("y" * pad) if pad else "{}"
    conn = db.connect(inventory)
    try:
        for table, want in (("cards", cards), ("boxes", boxes)):
            conn.execute(f"DELETE FROM {table}")
            for i in range(want):
                conn.execute(f"INSERT INTO {table} (key, payload) VALUES (?, ?)", (f"{table}-{i}", payload))
    finally:
        conn.close()


def damage(path: Path, page: int = 4) -> None:
    """Overwrite eight bytes of one page of a store file: SQLite's online backup copies that page without
    reading it, and only `PRAGMA integrity_check` notices."""
    data = bytearray(path.read_bytes())
    data[page * 4096:page * 4096 + 8] = b"\xff" * 8
    path.write_bytes(bytes(data))


def online_backup(store: Path, target: Path) -> None:
    """A finished copy of a store, made the way the job makes its snapshot, written to `target`."""
    target.parent.mkdir(parents=True, exist_ok=True)
    src = db.open_read_only(store)
    try:
        out = sqlite3.connect(target)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()


def sidecar_name():
    """The counts sidecar's file name, from the job's `SIDECAR` constant: a plain name of its own in the machine
    folder, beside the last-run line. None when the job has no such constant or it is not that."""
    name = job_constant("SIDECAR")
    plain = name and Path(name).name == name and name != "backup-last-run" and not name.endswith(".lock")
    return name if plain else None


def sidecar_state(case: Case):
    """(bytes, stat key) of the sidecar, or None when the job names none or the file is not there."""
    name = sidecar_name()
    path = case.home / ".banchi" / name if name else None
    return (path.read_bytes(), stat_key(path)) if path is not None and path.is_file() else None


def fake_checkout(case: Case, name: str, linked: bool) -> Path:
    """A copy of the job inside a fake checkout, so its `ROOT` (two folders up from the script) is that folder.
    The job and the shared installer are copies, because the job resolves its own path; the packages are
    links to the real ones. `.git` is a file in a linked worktree and a folder in the main tree."""
    root = case.root / name
    (root / "scripts").mkdir(parents=True)
    for entry in REPO_ROOT.iterdir():
        code = entry.suffix == ".py" or (entry.is_dir() and any(c.suffix == ".py" for c in entry.iterdir()))
        if code and entry.name != "scripts" and not entry.name.startswith("."):
            (root / entry.name).symlink_to(entry)
    for source in (SCRIPT, REPO_ROOT / "scripts" / "launchagent.py"):
        shutil.copyfile(source, root / "scripts" / source.name)
    if linked:
        (root / ".git").write_text("gitdir: /nowhere\n")
    else:
        (root / ".git").mkdir()
    return root / "scripts" / SCRIPT.name


#: Runs the job as `__main__` with its online backup killed (SIGKILL, no `finally`) after the first page.
KILL_MID_SNAPSHOT = """\
import os, runpy, signal, sys
sys.path[:0] = [{scripts!r}, {root!r}]
from store import db

real = db.open_read_only


class Killed:
    def __init__(self, conn):
        self.conn = conn

    def backup(self, target, **_):
        return self.conn.backup(target, pages=1, progress=lambda *_: os.kill(os.getpid(), signal.SIGKILL))

    def __getattr__(self, name):
        return getattr(self.conn, name)


db.open_read_only = lambda *a, **k: Killed(real(*a, **k))
sys.argv = [{job!r}]
runpy.run_path({job!r}, run_name="__main__")
"""


def run_killed_mid_snapshot(case: Case) -> Ran:
    wrapper = case.root / "kill_mid_snapshot.py"
    wrapper.write_text(KILL_MID_SNAPSHOT.format(scripts=str(SCRIPT.parent), root=str(REPO_ROOT), job=str(SCRIPT)))
    return run_job(case, cmd=[str(wrapper)])


# ------------------------------------------------------------------------------ the checks


@robust
def check_backup_run_folder_deletes_read_only_trees_and_follows_no_link(checks: Checks) -> None:
    """test-temp-standard: this check's files live in one `<pid>-<uuid>` run folder from the repo's one
    helper. The sweep of old siblings and the exit delete go through the same `remove_tree`, so a tree
    the cases made read-only goes too, and a link inside it is never followed to its target.
    (`t1_results` proves the sweep's keep rules: a new sibling and a stray name stay.)"""
    checks.note("")
    checks.note("NIGHTLY BACKUP — the group's temp files, then the job")
    checks.ok(
        RUN_FOLDER.parent == TEMP_ROOT and re.fullmatch(rf"{os.getpid()}-[0-9a-f-]{{36}}", RUN_FOLDER.name) is not None,
        "the check's temp files live in one <pid>-<uuid> run folder under the repo's one temp root",
        str(RUN_FOLDER),
    )
    if os.geteuid() == 0:
        checks.note("skipped: root deletes a 0500 folder without help, so the read-only case is not built")
        return
    outside = RUN_FOLDER / "outside"  # not under the siblings root; only a followed link could reach it
    (outside / "inner").mkdir(parents=True)
    (outside / "inner" / "file").write_text("x")
    outside.chmod(0o500)
    siblings = RUN_FOLDER / "siblings"
    old, new, old_link = (siblings / f"{n}-{uuid.uuid4()}" for n in (1, 2, 3))
    (old / "locked").mkdir(parents=True)
    (old / "locked" / "file").write_text("x")
    (old / "link").symlink_to(outside)
    (old / "locked").chmod(0o500)
    new.mkdir()
    old_link.symlink_to(outside)
    stamp = time.time() - 2 * DAY
    os.utime(old, (stamp, stamp))
    os.utime(old_link, (stamp, stamp), follow_symlinks=False)
    os.utime(outside, (stamp, stamp))
    with run_folder(siblings) as mine:
        checks.ok(not old.exists() and new.exists(), "the sweep removes an old sibling, even a read-only one, and keeps a new one",
                  f"old exists={old.exists()}, new exists={new.exists()}")
        checks.ok(old_link.is_symlink(), "and a link named like a run folder is left alone, not swept")
        (mine / "locked").mkdir()
        (mine / "locked" / "file").write_text("x")
        (mine / "link").symlink_to(outside)
        (mine / "locked").chmod(0o500)
    checks.ok(not mine.exists(), "the exit removes this run's folder, even with a read-only tree in it",
              f"exists={mine.exists()}")
    checks.ok(
        (outside / "inner" / "file").is_file() and outside.stat().st_mode & 0o777 == 0o500,
        "and no delete followed a link: the link's target keeps its file and its read-only mode",
        f"mode={oct(outside.stat().st_mode & 0o777)}",
    )


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
    checks.equal(strays(case), [], "the destination holds no -wal, -shm or temp file beside the snapshots")
    checks.ok(finished and before and before == after, "the source store file and its -wal are byte for byte what they were", f"{before} / {after}")
    checks.ok(finished and survived == 5, "the writer's transaction was not disturbed: it commits after the job", str(survived))


@robust
def check_backup_copies_and_skips_by_stat(checks: Checks) -> None:
    """Photographs and captures are copied once. An unchanged file is not rewritten, and neither is a changed one:
    it is left as it is and fails the run (`check_backup_a_changed_source_file_never_overwrites_its_copy` takes the
    rest of that rule)."""
    case = Case("copy")
    seed_store(case)
    seed_files(case)
    first = run_job(case)
    expect_ok(checks, "first night: all five files copied, none skipped", first, case, copied=5, skipped=0)
    same = {rel: (dest_path.read_bytes() == FILES.get(rel)) for rel, dest_path in dest_files(case).items() if rel in FILES}
    checks.ok(len(same) == 5 and all(same.values()), "every photograph and capture is in the destination, byte for byte, under its own path")
    checks.ok(NIGHTLY in dest_files(case) and strays(case) == [], "the snapshot is there and nothing else: no temp file, no stray", str(strays(case)))
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
    failed = expect_differs(checks, "third night, one file changed and one added: exit non-zero and a failed line that names 1 differing file",
                            third, case, 1)
    got = dest_files(case)
    checks.ok(
        failed and changed in got and got[changed].read_bytes() == FILES[changed] and stat_key(got[changed]) == stats[changed],
        "a source file with the same size and a newer mtime does not replace its copy: bytes, inode, size, mtime and ctime are as they were",
    )
    checks.ok(failed and "photos/ff/ff00ee330003.jpg" in got, "and the new photograph is copied")
    checks.ok(
        failed and all(rel in stats and rel in got and stats[rel] == stat_key(got[rel]) for rel in FILES if rel != changed),
        "the four unchanged files still were not rewritten",
    )
    checks.ok(failed and source_before == fingerprint(case.src), "the source files are as the job found them")


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
        open_up(case.dest)


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
    left = strays(case)
    checks.ok(failed and left == [], "and no half-written temp file is left in the destination", str(left))
    checks.ok(failed and garbage == fingerprint(case.src), "and the source store file was not touched")


@robust
def check_backup_default_destination_is_the_icloud_folder(checks: Checks) -> None:
    """With no override the destination is `Banchi backup` in iCloud Drive. When iCloud Drive is off its
    folder is absent: the run fails and creates nothing, so a local folder that never syncs is never made.
    Both runs use a copy of the job in a fake main-tree checkout: the job refuses a linked worktree when the
    destination is not overridden (see `check_backup_refuses_a_linked_worktree`)."""
    case = Case("icloud")
    seed_store(case)
    seed_files(case)
    job = [str(fake_checkout(case, "main-tree", linked=False))]
    off = run_job(case, dest=None, cmd=job)
    failed = expect_failed(checks, "iCloud Drive off (its folder is absent): a failed run", off, case)
    checks.ok(failed and not (case.home / "Library" / "Mobile Documents").exists(), "and no Library/Mobile Documents is made")

    case.icloud_root.mkdir(parents=True, exist_ok=True)
    on = run_job(case, dest=None, cmd=job)
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
    wanted = sorted({"backup-last-run", sidecar_name()} - {None})
    checks.equal(others, wanted, "a run writes the last-run file and the counts sidecar (if the job names one) in the machine folder, and no log, beside an optional lock")


def status_line_under_test(name: str):
    """The job's `status_line`, loaded alone (its `import launchagent` needs `scripts/` on the path). The caller
    sets HOME: the last-run file is read from `~/.banchi` when the function is called."""
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, SCRIPT)
        job = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(job)
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return job.status_line


@robust
def check_backup_status_shows_the_last_run(checks: Checks) -> None:
    """`make status` prints the last-run line, and says so when no backup has run. The job's `status_line`
    is called alone, with HOME in the run folder."""
    case = Case("status")
    status_line = status_line_under_test("_banchi_status_under_test")
    word = lambda text: re.search(r"\bok\b", text) is not None  # noqa: E731

    raised = []

    def section() -> str:
        try:
            return status_line()
        except Exception as exc:  # noqa: BLE001 - no `status_line` yet reads as failed lines, not a traceback
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
        not raised and all(token in good for token in ("2026-10-24T03:00:12", "copied=12", "skipped=34")) and word(good),
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
    docstrings = {
        id(n.body[0].value) for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
        and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)
    }
    direct = sorted({
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and "launchctl" in n.value and id(n) not in docstrings
    })
    checks.ok(not direct, "the job never names launchctl itself: only the shared helper calls it", str(direct))
    if labels != [LABEL] or not helper or direct:
        return  # `agent` runs below only when the helper is the sole way to launchctl; a second way could install a real job

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


@robust
def check_backup_one_bad_file_does_not_stop_the_run(checks: Checks) -> None:
    """Files in photos/ that cannot be read (a link whose target is gone, a file with no read permission)
    fail the night but never stop it: the rest are copied, the store is snapshotted fresh, and the last-run
    line says `failed` with how many files were bad. One bad file must not cost the owner the night's backup."""
    case = Case("bad-file")
    seed_store(case)
    seed_files(case)
    control = expect_ok(checks, "control: the first night is ok", run_job(case), case, copied=5, skipped=0)
    add_row(case, "after-night-1")
    new = "photos/ff/ff00ee330003.jpg"
    put(case.src, new, b"\xff\xd8\xff" + b"E" * 400)
    bad = []
    for name in ("dd/dd0000000001.jpg", "dd/dd0000000002.jpg"):
        link = case.src / "photos" / name
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(case.root / "gone" / name)
        bad.append(link)
    locked = put(case.src, "photos/ee/ee0000000003.jpg", b"\xff\xd8\xff" + b"L" * 200)
    locked.chmod(0)
    if os.access(locked, os.R_OK):  # running as root: the mode does not bite, so the third bad file is another dead link
        locked.chmod(0o644)
        locked.unlink()
        locked.symlink_to(case.root / "gone" / "ee0000000003.jpg")
    bad.append(locked)
    try:
        ran = run_job(case)
    finally:
        if locked.exists() and not locked.is_symlink():
            locked.chmod(0o644)
    failed = expect_failed(checks, "three bad files in photos/: exit non-zero and a failed line", ran, case)
    raw = (last_run(case) or {}).get("raw") or ""
    reason = raw.replace(str(case.root), "").replace(str(case.root.resolve()), "")
    checks.ok(failed and re.search(rf"\b{len(bad)}\b", reason) is not None, f"and the line carries the count of bad files ({len(bad)})", repr(raw))
    rows, integrity = snapshot_view(case)
    checks.ok(control and rows is not None and rows == store_rows(case) and integrity == [("ok",)],
              "and the snapshot is still made, fresh: it holds the row added since the first night", str(integrity))
    got = dest_files(case)
    checks.ok(control and new in got and got[new].read_bytes() == b"\xff\xd8\xff" + b"E" * 400,
              "and the good photograph added since is copied, byte for byte")
    checks.ok(control and all(rel in got and got[rel].read_bytes() == data for rel, data in FILES.items()),
              "and the first night's five files are still in the destination, unchanged")


@robust
def check_backup_refuses_a_linked_worktree(checks: Checks) -> None:
    """The job is for the owner's main tree. In a linked worktree (`ROOT/.git` is a file) with no destination
    override it refuses and writes nothing to the default iCloud folder. The control runs the same fake
    checkout as a main tree (`.git` a folder), so the refusal cannot be an import error or a missing script."""
    case = Case("linked")
    seed_store(case)
    seed_files(case)
    case.icloud_root.mkdir(parents=True)  # iCloud Drive is on, so a job that does not refuse has somewhere to write
    target = case.icloud_root / "Banchi backup"
    main_job = fake_checkout(case, "main-tree", linked=False)
    linked_job = fake_checkout(case, "linked-tree", linked=True)
    ran = run_job(case, dest=None, cmd=[str(main_job)])
    control = expect_ok(checks, "control: from a main tree with no override, the job writes to the default folder", ran, case, copied=5, skipped=0)
    control = control and (target / NIGHTLY).is_file()
    checks.ok(control, "control: its snapshot is in 'Banchi backup' inside iCloud Drive")
    if not control:
        return
    remove_tree(target)
    ran = run_job(case, dest=None, cmd=[str(linked_job)])
    said_why = re.search(r"worktree|linked", ran.out + ran.err, re.I) is not None
    checks.ok(ran.code not in (0, None) and said_why, "from a linked worktree with no override: non-zero, and it says it is a worktree", said(ran))
    checks.ok(not target.exists() and not any(case.icloud_root.iterdir()), "and nothing is written to the default destination")


@robust
def check_backup_missing_photos_tree_is_a_failure(checks: Checks) -> None:
    """A source with no `photos/` folder (a wrong BANCHI_HOME, an unmounted drive) is a failed run. Walking
    a folder that is not there finds nothing, which would read as `ok copied=0` and hide the loss."""
    case = Case("no-photos")
    seed_store(case)
    seed_files(case)
    control = expect_ok(checks, "control: the first night is ok", run_job(case), case, copied=5, skipped=0)
    shutil.rmtree(case.src / "photos")
    ran = run_job(case)
    failed = expect_failed(checks, "a source with no photos/ tree: exit non-zero and a failed line, not ok copied=0", ran, case)
    got = dest_files(case)
    checks.ok(control and failed and all(rel in got for rel in FILES), "and the photographs already in the destination are still there")


@robust
def check_backup_status_flags_an_old_last_run(checks: Checks) -> None:
    """`make status` must not show last month's `ok` as if it were last night's: a last-run line older than
    36 hours carries the word `stale`, a younger one does not. Both the
    line's own time and the file's mtime are set, so either clock a build reads gives the same answer."""
    case = Case("status-old")
    status_line = status_line_under_test("_banchi_status_old_under_test")
    raised = []

    def section(hours: float) -> str:
        then = time.time() - hours * 3600
        case.last_run_file.parent.mkdir(parents=True, exist_ok=True)
        case.last_run_file.write_text(f"{time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(then))} ok copied=12 skipped=34\n")
        os.utime(case.last_run_file, (then, then))
        try:
            with mock.patch.dict(os.environ, {"HOME": str(case.home)}):
                return status_line()
        except Exception as exc:  # noqa: BLE001 - no `status_line` yet reads as failed lines, not a traceback
            raised.append(f"{type(exc).__name__}: {exc}")
            return ""

    stale = lambda text: re.search(r"\bstale\b", text, re.I) is not None  # noqa: E731
    fresh, edge, old = section(2), section(30), section(40)
    checks.ok(not raised and "copied=12" in fresh and not stale(fresh), "a line from 2 hours ago is shown and not flagged", fresh or str(raised))
    checks.ok(not raised and "copied=12" in edge and not stale(edge), "a line from 30 hours ago is still not flagged", edge or str(raised))
    checks.ok(not raised and "copied=12" in old and stale(old), "a line from 40 hours ago is shown and flagged stale", old or str(raised))


@robust
def check_backup_mtimes_within_two_seconds_are_equal(checks: Checks) -> None:
    """A synced folder rounds mtimes, so a destination file whose mtime is within 2 s of the source's, either
    way, is the same file and is skipped. The size must still match and a larger gap is still a change: a
    differing file is left untouched and fails the run (never rewritten), and the three within 2 s are not
    counted as differing."""
    case = Case("mtime-slack")
    seed_store(case)
    seed_files(case)
    expect_ok(checks, "first night copies the five files", run_job(case), case, copied=5, skipped=0)
    dest = {rel: p for rel, p in dest_files(case).items() if rel in FILES}
    ahead, behind, same = "photos/6b/6b1cf2fd0001.jpg", "photos/a0/a0aa11220002.jpg", "captures/cards/box1/0001.jpg"
    apart, resized = "captures/cards/box1/0001.json", "captures/cards/box2/0001.jpg"
    halves = SECOND * 3 // 2
    os.utime(dest[ahead], ns=(T0 + halves,) * 2)
    os.utime(dest[behind], ns=(T0 - halves,) * 2)
    os.utime(dest[apart], ns=(T0 - 5 * SECOND,) * 2)
    dest[resized].write_bytes(b"short")  # another size, mtime a second off
    os.utime(dest[resized], ns=(T0 + SECOND,) * 2)
    kept = {rel: stat_key(dest[rel]) for rel in (ahead, behind, same, apart, resized)}
    ran = run_job(case)
    failed = expect_differs(checks, "next night: the file 5 s apart and the file of another size fail the run as 2 differing files, the three within 2 s are not counted",
                            ran, case, 2)
    got = dest_files(case)
    checks.ok(failed and all(rel in got and kept[rel] == stat_key(got[rel]) for rel in (ahead, behind, same)),
              "a destination file 1.5 s ahead, 1.5 s behind or equal is not rewritten")
    checks.ok(failed and all(rel in got and kept[rel] == stat_key(got[rel]) for rel in (apart, resized))
              and got[apart].read_bytes() == FILES[apart] and got[resized].read_bytes() == b"short",
              "the file 5 s apart and the file of another size are left as they were: not rewritten, not repaired")


@robust
def check_backup_snapshot_is_built_outside_the_destination(checks: Checks) -> None:
    """The destination is a synced folder: a half-written temp file or journal there would sync as if it were
    a backup. A run killed in the middle of the online backup (SIGKILL, so no `finally` runs) leaves the
    destination exactly as the last good night left it. The kill is simulated by a wrapper that dies after the
    first page; the control proves the job runs through the same wrapper path when not killed."""
    case = Case("killed")
    seed_store(case, rows=9)
    seed_files(case)
    control = expect_ok(checks, "control: the first night is ok", run_job(case), case, copied=5, skipped=0)
    nightly = case.dest / NIGHTLY
    good = sha(nightly) if nightly.is_file() else None
    entries = lambda: sorted(p.relative_to(case.dest).as_posix() for p in case.dest.rglob("*"))  # noqa: E731
    before = entries()
    add_row(case, "after-night-1")
    ran = run_killed_mid_snapshot(case)
    checks.ok(control and ran.code == -signal.SIGKILL, "the simulated kill bit: the job died of SIGKILL inside its online backup", said(ran))
    after = entries()
    checks.ok(control and ran.code == -signal.SIGKILL and after == before,
              "the destination holds exactly what it held before: no temp file, journal or folder was left in it",
              f"left behind: {sorted(set(after) - set(before))}")
    checks.ok(control and good is not None and nightly.is_file() and sha(nightly) == good, "and last night's snapshot is there, byte for byte")
    again = run_job(case)
    expect_ok(checks, "the next normal night is ok", again, case, copied=0, skipped=5)
    rows, integrity = snapshot_view(case)
    checks.ok(rows is not None and rows == store_rows(case) and integrity == [("ok",)], "and its snapshot is fresh again", str(integrity))


@robust
def check_backup_keeps_a_nightly_and_a_weekly_snapshot(checks: Checks) -> None:
    """Owner ruling: two store snapshots, a week apart at the widest. The nightly is replaced every run. The
    weekly is made the first night and then replaced only when its file is 7 days old or more, from that night's
    good snapshot. A night whose snapshot fails replaces neither. The weekly's age is its file's mtime, which
    the case moves with `utime`; the job never opens a destination file to learn it."""
    case = Case("weekly")
    seed_store(case)
    seed_files(case)
    rel = weekly_rel()
    checks.ok(rel is not None, "the job names the weekly snapshot's path in a WEEKLY_SNAPSHOT constant: a relative path of its own", repr(job_constant("WEEKLY_SNAPSHOT")))
    if rel is None:
        return
    weekly = case.dest / rel
    rows_of = lambda name: snapshot_view(case, name)[0]  # noqa: E731

    expect_ok(checks, "night 1: ok", run_job(case), case, copied=5, skipped=0)
    night1 = store_rows(case)
    checks.ok(rows_of(NIGHTLY) == night1 and rows_of(rel) == night1, "night 1 makes both snapshots, each equal to the store")
    checks.equal(strays(case), [], "and the destination holds those two and nothing else beside the five files")

    add_row(case, "night-2")
    kept = stat_key(weekly)
    expect_ok(checks, "night 2: ok", run_job(case), case, copied=0, skipped=5)
    checks.ok(rows_of(NIGHTLY) == store_rows(case), "night 2: the nightly is replaced, it holds night 2's row")
    checks.ok(rows_of(rel) == night1 and kept == stat_key(weekly), "night 2: the weekly is not touched, it is a day old")

    age(weekly, 6)
    add_row(case, "night-3")
    kept = stat_key(weekly)
    expect_ok(checks, "night 3, the weekly 6 days old: ok", run_job(case), case, copied=0, skipped=5)
    checks.ok(rows_of(NIGHTLY) == store_rows(case), "night 3: the nightly is replaced")
    checks.ok(rows_of(rel) == night1 and kept == stat_key(weekly), "night 3: the weekly, 6 days old, is not touched")

    age(weekly, 8)
    add_row(case, "night-4")
    expect_ok(checks, "night 4, the weekly 8 days old: ok", run_job(case), case, copied=0, skipped=5)
    now, weekly_rows = store_rows(case), snapshot_view(case, rel)
    checks.ok(rows_of(NIGHTLY) == now and weekly_rows[0] == now and weekly_rows[1] == [("ok",)],
              "night 4: the weekly is replaced from that night's snapshot, whole, and holds every row added since night 1")
    checks.ok(abs(time.time() - weekly.stat().st_mtime) < 300, "and the new weekly is dated now, so the next week counts from here")
    checks.equal(strays(case), [], "and still only the two snapshots are there")

    age(weekly, 8)
    kept, last_nightly = stat_key(weekly), sha(case.dest / NIGHTLY)
    (case.src / "inventory" / "store.sqlite").write_bytes(b"this is not a database " * 200)
    ran = run_job(case)
    failed = expect_failed(checks, "night 5, the store cannot be snapshotted and the weekly is due: exit non-zero and a failed line", ran, case)
    checks.ok(failed and sha(case.dest / NIGHTLY) == last_nightly, "a failed night leaves the nightly as night 4 made it, byte for byte")
    checks.ok(failed and kept == stat_key(weekly), "and leaves the due weekly as it was: a failed night never replaces either")
    checks.equal(strays(case), [], "and no temp file is left")


#: (table, rows it falls to from SIZE, whether the night must fail). "More than half" is strict: exactly half is fine.
DROPS = (("cards", 4, True), ("boxes", 1, True), ("cards", 5, False), ("boxes", 2, False))


@robust
def check_backup_a_store_that_shrank_replaces_neither_snapshot(checks: Checks) -> None:
    """DEBT67: a store emptied by a bug or a bad restore must not overwrite the two snapshots that could undo it.
    On a night the weekly is due, a `cards` or `boxes` count more than half below the last good run's (kept in a
    sidecar beside the last-run line) replaces neither snapshot, fails the night, and keeps the sidecar, so the
    next night still compares to the last good run. Each table is dropped alone, so a guard on one fails the other.
    The destination's nightly already holds the dropped store before the night, so a job that took its counts from
    the destination would see no drop. Exactly half is still a good night: it replaces both and moves the sidecar."""
    rel = weekly_rel()
    for table, after, fails in DROPS:
        label = f"{table} {SIZE[table]} to {after}"
        case = Case(f"shrink-{table}-{after}")
        seed_store(case)
        seed_counts(case.src / "inventory", **SIZE)
        seed_files(case)
        expect_ok(checks, f"{label}: night 1 is ok", run_job(case), case, copied=5, skipped=0)
        good = sidecar_state(case)
        checks.ok(good is not None, f"{label}: a good night leaves the counts sidecar beside the last-run line", f"SIDECAR = {job_constant('SIDECAR')!r}")
        nightly, weekly = case.dest / NIGHTLY, case.dest / rel
        seed_counts(case.src / "inventory", **{**SIZE, table: after})
        online_backup(case.src / "inventory" / "store.sqlite", case.root / "dropped.sqlite")
        shutil.copyfile(case.root / "dropped.sqlite", nightly)
        age(weekly, 8)
        kept = (stat_key(nightly), stat_key(weekly))
        if fails:
            for night in (2, 3):
                night_label = f"{label}, night {night}, the weekly 8 days old"
                expect_failed(checks, f"{night_label}: exit non-zero and a failed line", run_job(case), case)
                checks.ok((stat_key(nightly), stat_key(weekly)) == kept, f"{night_label}: neither snapshot is replaced")
                checks.ok(good is not None and sidecar_state(case) == good, f"{night_label}: the sidecar is as the last good night left it")
                checks.equal(strays(case), [], f"{night_label}: no temp file is left")
        else:
            expect_ok(checks, f"{label}, night 2, the weekly 8 days old: ok", run_job(case), case, copied=0, skipped=5)
            checks.ok(stat_key(nightly) != kept[0], f"{label}: the nightly is replaced")
            view = snapshot_view(case, rel)
            checks.ok(view[0] == store_rows(case) and stat_key(weekly) != kept[1] and abs(time.time() - weekly.stat().st_mtime) < 300,
                      f"{label}: the due weekly is replaced from that night's snapshot", str(view[1]))
            now = sidecar_state(case)
            checks.ok(good is not None and now is not None and now[0] != good[0], f"{label}: the sidecar moves to this night's counts")


@robust
def check_backup_an_unreadable_photo_folder_fails_the_night(checks: Checks) -> None:
    """`os.walk` skips a folder it cannot list without a word, so a `photos/` shard with no read permission would
    read as `ok copied=N` and hide the cards inside it. The folder counts as one bad file: the night fails, the rest
    is copied and snapshotted, and once the folder is readable again the next night copies what was in it."""
    case = Case("unreadable-folder")
    seed_store(case)
    seed_files(case)
    control = expect_ok(checks, "control: the first night is ok", run_job(case), case, copied=5, skipped=0)
    add_row(case, "after-night-1")
    new = "photos/ff/ff00ee330003.jpg"
    put(case.src, new, b"\xff\xd8\xff" + b"E" * 400)
    hidden = "photos/dd/dd0000000001.jpg"
    folder = put(case.src, hidden, b"\xff\xd8\xff" + b"H" * 300).parent
    folder.chmod(0)
    try:
        if os.access(folder, os.R_OK):  # running as root: a mode does not bite and there is no stand-in for a folder
            checks.ok(True, "SKIPPED, running as root: a folder with mode 0 is still readable")
            return
        ran = run_job(case)
    finally:
        folder.chmod(0o755)
    failed = expect_failed(checks, "a photos/ subfolder with no read permission: exit non-zero and a failed line", ran, case)
    raw = (last_run(case) or {}).get("raw") or ""
    reason = re.sub(r"^\S+ failed", "", raw.replace(str(case.root), "").replace(str(case.root.resolve()), ""))
    checks.ok(failed and re.search(r"\b1\b", reason) is not None, "and the line counts the folder as one bad file", repr(raw))
    rows, integrity = snapshot_view(case)
    checks.ok(control and rows is not None and rows == store_rows(case) and integrity == [("ok",)],
              "and the snapshot is still made, fresh: it holds the row added since the first night", str(integrity))
    got = dest_files(case)
    checks.ok(control and new in got and got[new].read_bytes() == b"\xff\xd8\xff" + b"E" * 400,
              "and the good photograph added since is copied, byte for byte")
    checks.ok(control and all(rel in got and got[rel].read_bytes() == data for rel, data in FILES.items()),
              "and the first night's five files are still in the destination, unchanged")
    expect_ok(checks, "once the folder is readable again the next night is ok", run_job(case), case, copied=1, skipped=6)
    checks.ok(hidden in dest_files(case), "and the photograph that was inside the folder is now in the destination")


@robust
def check_backup_a_linked_worktree_with_a_destination_leaves_the_machine_folder_alone(checks: Checks) -> None:
    """`~/.banchi` is shared by every checkout (D43). A linked worktree may run the job against a destination of its
    own (that is what the override is for), but a test run there must not overwrite the owner's real last-run line
    or counts sidecar: it writes nothing to the machine folder but an optional lock. The control is the main tree
    with a destination set, which does write the last-run line, so an empty folder below is not a wrong folder."""
    case = Case("linked-dest")
    seed_store(case)
    seed_files(case)
    main_job = fake_checkout(case, "main-tree", linked=False)
    linked_job = fake_checkout(case, "linked-tree", linked=True)
    control = expect_ok(checks, "control: the main tree with a destination set records its night in the machine folder",
                        run_job(case, dest=case.root / "main-dest", cmd=[str(main_job)]), case, copied=5, skipped=0)
    machine = case.home / ".banchi"
    shutil.rmtree(machine, ignore_errors=True)
    ran = run_job(case, cmd=[str(linked_job)])
    got = dest_files(case)
    ran_ok = checks.ok(control and ran.code == 0 and snapshot_view(case)[0] == store_rows(case)
                       and all(rel in got and got[rel].read_bytes() == data for rel, data in FILES.items()),
                       "a linked worktree with a destination set still runs: exit 0, the five files and the snapshot are in it", said(ran))
    left = sorted(p.name for p in machine.iterdir() if not p.name.endswith(".lock")) if machine.is_dir() else []
    checks.ok(ran_ok and left == [], "and it writes no last-run line and no sidecar to the machine folder", repr(left))


@robust
def check_backup_a_changed_source_file_never_overwrites_its_copy(checks: Checks) -> None:
    """DEBT67, a good copy is never replaced by a bad one. A destination file that exists with another size or
    mtime than its source (a re-shoot, D26, looks like this) is never rewritten, whichever way it differs: the run
    ends `failed` and names how many files it left alone, the walk goes on, and the next run fails the same way.
    One file differs by size and one by mtime alone, so a job that compares only one of them leaves the other
    overwritten. The control is the first run, which copies all five, so a job that did nothing cannot pass."""
    case = Case("differs")
    seed_store(case)
    seed_files(case)
    control = expect_ok(checks, "control: the first night copies the five files", run_job(case), case, copied=5, skipped=0)
    resized, touched = "photos/a0/a0aa11220002.jpg", "captures/cards/box1/0001.jpg"
    put(case.src, resized, FILES[resized] + b"more")  # another size
    put(case.src, touched, FILES[touched], mtime=T0 + 60 * SECOND)  # the same bytes, a minute newer
    new = "photos/ff/ff00ee330003.jpg"
    put(case.src, new, b"\xff\xd8\xff" + b"E" * 400)
    kept = {rel: (p.read_bytes(), stat_key(p)) for rel, p in dest_files(case).items() if rel in FILES}
    source = fingerprint(case.src)
    ran = run_job(case)
    failed = expect_differs(checks, "two source files differ from their copies: exit non-zero and a failed line that names the count of 2",
                            ran, case, 2)
    got = dest_files(case)
    checks.ok(control and failed and len(kept) == 5 and all(rel in got and (got[rel].read_bytes(), stat_key(got[rel])) == kept[rel] for rel in kept),
              "every destination file is untouched: bytes, inode, size, mtime and ctime")
    checks.ok(control and failed and new in got and got[new].read_bytes() == b"\xff\xd8\xff" + b"E" * 400,
              "the walk goes on: a file missing from the destination is still copied")
    checks.ok(failed and source == fingerprint(case.src), "the source is as the job found it")
    again = expect_differs(checks, "the next night still fails with the same count: the differs are not forgotten", run_job(case), case, 2)
    got = dest_files(case)
    checks.ok(control and again and all(rel in got and (got[rel].read_bytes(), stat_key(got[rel])) == kept[rel] for rel in kept),
              "and still leaves both copies alone")


@robust
def check_backup_a_damaged_store_is_refused_and_replaces_nothing(checks: Checks) -> None:
    """DEBT67: SQLite's online backup copies a damaged page without reading it, so the finished snapshot must pass
    `PRAGMA integrity_check` before anything is moved in. A store that fails it replaces the nightly, the weekly and
    the dated copy with nothing, fails the run, and leaves the photographs copied. On a first run it leaves no store
    copy of any name. The weekly is aged to be due and the fixture is shown to tell a sound store from a damaged one,
    so a job that skipped the check, or a check that always fails, cannot pass."""
    case = Case("damaged")
    seed_store(case)
    seed_counts(case.src / "inventory", cards=400, boxes=0, pad=200)  # enough pages that page 4 holds data
    seed_files(case)
    sound = case.root / "sound.sqlite"
    online_backup(case.src / "inventory" / "store.sqlite", sound)
    checks.ok(integrity_ok(case, sound), "the fixture's sound store passes the integrity check on its own")
    control = expect_ok(checks, "control: the first night, from a sound store, is ok", run_job(case), case, copied=5, skipped=0)
    made = dated_copies(case)
    nightly, weekly = case.dest / NIGHTLY, case.dest / (weekly_rel() or "no-weekly")
    kept = None
    if control and weekly.is_file():
        age(weekly, 8)  # the weekly is due, so a night that did not refuse would replace it
        kept = (sha(nightly), sha(weekly), stat_key(nightly), stat_key(weekly), {rel: stat_key(case.dest / rel) for rel in made})
    damage(case.src / "inventory" / "store.sqlite")
    checks.ok(not integrity_ok(case, case.src / "inventory" / "store.sqlite"), "the damaged store fails the integrity check on its own")
    new = "photos/ff/ff00ee330003.jpg"
    put(case.src, new, b"\xff\xd8\xff" + b"E" * 400)
    ran = run_job(case)
    failed = expect_failed(checks, "a damaged store: exit non-zero and a failed line", ran, case)
    checks.ok(failed and kept is not None and dated_copies(case) == made and sha(nightly) == kept[0] and sha(weekly) == kept[1]
              and (stat_key(nightly), stat_key(weekly)) == kept[2:4] and {rel: stat_key(case.dest / rel) for rel in made} == kept[4],
              "the nightly, the weekly and the dated copy are as the last good night left them: byte for byte, inode and mtime")
    checks.ok(failed and (case.dest / new).is_file(), "and the photographs are still copied")

    fresh = Case("damaged-first")
    seed_store(fresh)
    seed_counts(fresh.src / "inventory", cards=400, boxes=0, pad=200)
    seed_files(fresh)
    damage(fresh.src / "inventory" / "store.sqlite")
    ran = run_job(fresh)
    failed = expect_failed(checks, "a damaged store on a first night: exit non-zero and a failed line", ran, fresh)
    stores = sorted(rel for rel in dest_files(fresh) if rel.startswith("inventory/"))
    checks.ok(failed and stores == [] and all(rel in dest_files(fresh) for rel in FILES),
              "no store copy of any name is written, while the photographs are", repr(stores))


@robust
def check_backup_a_dated_store_copy_is_written_once_and_never_replaced(checks: Checks) -> None:
    """DEBT67: besides the nightly and the weekly the destination holds one copy named by the day,
    in the job's `DATED_SNAPSHOT` path. It is written once per local day and never replaced: a second run the same
    day keeps the day's first copy byte for byte, while the nightly (a paired positive) moves on to the new row."""
    case = Case("dated")
    seed_store(case)
    seed_files(case)
    template = job_constant("DATED_SNAPSHOT")
    named = checks.ok(dated_pattern() is not None, "the job names the dated copy's path in a DATED_SNAPSHOT constant with one %s", repr(template))
    day = time.strftime("%Y-%m-%d")
    expect_ok(checks, "the first night is ok", run_job(case), case, copied=5, skipped=0)
    after = time.strftime("%Y-%m-%d")  # a run over midnight may name either day
    names = dated_copies(case)
    wanted = {template % d for d in (day, after)} if named else set()
    checks.ok(len(names) == 1 and names[0] in wanted, "it writes one store copy named by the day", repr(names))
    if len(names) != 1:
        return
    rows, integrity = snapshot_view(case, names[0])
    checks.ok(rows == store_rows(case) and integrity == [("ok",)], "and the copy is whole and holds every row")
    first = (sha(case.dest / names[0]), stat_key(case.dest / names[0]))
    add_row(case, "after-night-1")
    expect_ok(checks, "a second run the same day is ok", run_job(case), case, copied=0, skipped=5)
    checks.ok(snapshot_view(case)[0] == store_rows(case), "the second run did snapshot: the nightly holds the new row")
    checks.ok(dated_copies(case) == names and (sha(case.dest / names[0]), stat_key(case.dest / names[0])) == first,
              "and the day's copy is not replaced: same bytes, same inode, same mtime")


@robust
def check_backup_verify_flags_a_flipped_byte_and_a_missing_file(checks: Checks) -> None:
    """DEBT67: `--verify` hashes the source against the destination, so a byte flipped under an unchanged size and
    mtime is seen, which the default run (stat only) cannot. It exits 0 only on a clean copy, names each bad path,
    and writes nothing. The clean copy is the paired positive: the mismatch and missing runs are the same copy
    with one file each damaged, so an exit-2 from an unknown flag cannot pass for them."""
    case = Case("verify")
    seed_store(case)
    seed_files(case)
    control = expect_ok(checks, "control: the first night copies the five files", run_job(case), case, copied=5, skipped=0)
    ran = run_job(case, args=["--verify"])
    clean = checks.ok(control and ran.code == 0 and "matches=5 mismatches=0 missing=0" in ran.out and "integrity=ok" in ran.out,
                      "on a clean copy: exit 0, five matches, no mismatch, none missing, the dated copy ok", said(ran) + ran.out)
    flipped, gone = "photos/a0/a0aa11220002.jpg", "captures/cards/box1/0001.json"
    path = case.dest / flipped
    stat = path.stat()
    data = bytearray(path.read_bytes())
    data[10] ^= 1
    path.write_bytes(bytes(data))
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))  # the size and mtime are as they were
    (case.dest / gone).unlink()
    machine = case.home / ".banchi"

    def state():
        return ({rel: (p.read_bytes(), stat_key(p)) for rel, p in dest_files(case).items()},
                {p.name: (p.read_bytes(), stat_key(p)) for p in machine.iterdir() if p.is_file() and p.suffix != ".lock"})
    before = state()
    ran = run_job(case, args=["--verify"])
    checks.ok(clean and ran.code not in (0, None) and "mismatches=1" in ran.out and "missing=1" in ran.out
              and flipped in ran.out and gone in ran.out,
              "a flipped byte and a deleted file: exit non-zero, one mismatch and one missing, both paths named", said(ran) + ran.out)
    checks.ok(clean and before == state(), "and verify wrote nothing: the destination and the machine folder are as they were")
    put(case.dest, gone, FILES[gone])
    path.write_bytes(FILES[flipped])
    names = dated_copies(case)
    if clean and names:
        (case.dest / names[-1]).write_bytes(b"this is not a database " * 200)
        ran = run_job(case, args=["--verify"])
        checks.ok(ran.code not in (0, None) and "matches=5 mismatches=0 missing=0" in ran.out and "integrity=bad" in ran.out,
                  "a damaged newest store copy, every file matching: exit non-zero and the copy reads bad", said(ran) + ran.out)


CHECKS = (
    check_backup_run_folder_deletes_read_only_trees_and_follows_no_link,
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
    check_backup_one_bad_file_does_not_stop_the_run,
    check_backup_refuses_a_linked_worktree,
    check_backup_missing_photos_tree_is_a_failure,
    check_backup_status_flags_an_old_last_run,
    check_backup_mtimes_within_two_seconds_are_equal,
    check_backup_snapshot_is_built_outside_the_destination,
    check_backup_keeps_a_nightly_and_a_weekly_snapshot,
    check_backup_a_store_that_shrank_replaces_neither_snapshot,
    check_backup_an_unreadable_photo_folder_fails_the_night,
    check_backup_a_linked_worktree_with_a_destination_leaves_the_machine_folder_alone,
    check_backup_a_changed_source_file_never_overwrites_its_copy,
    check_backup_a_damaged_store_is_refused_and_replaces_nothing,
    check_backup_a_dated_store_copy_is_written_once_and_never_replaced,
    check_backup_verify_flags_a_flipped_byte_and_a_missing_file,
)
