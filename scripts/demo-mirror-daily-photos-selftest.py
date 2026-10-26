#!/usr/bin/env python3
# Protects: The daily demo mirror never publishes a bundle that names a card whose photograph it did not commit, and removes its throwaway worktree on every exit path. The public demo shows a buyer as first name plus last initial and still refuses any surname or address; a deploy holds the last good demo when the recording's wire digest differs from the tree's; the mirror refreshes weekly.
"""The daily mirror ships every photograph its bundle names (D295, D172).
Incident: `.gitignore`'s bare `photos` also matched demo-assets/mirror/photos/, `git add` skipped
the new photographs without a word, and the bundle merged naming cards with no photograph.
Three cases, each red on the old code.

The same file proves the throwaway worktree (`.claude/worktrees/demo-mirror-daily-<epoch>`) is gone
after `run()`. Incident: the owner's disk held leftover folders of that name, some whole trees and
some only a stub `demo/inventory/match-sweep.json`. `run()`'s `finally` runs `git worktree remove
--force` with `check=False` and never looks whether the folder is gone. The demo server's sweep
watcher starts inside the tree and keeps rewriting that record, so removal fails or the folder
comes back. Five cases, each through `run()`: unchanged, Stop, unexpected error, merged, and a
background writer left in the tree. Each asserts no folder, no git registration and no admin entry
remain.

The last block, `policy_rulings()`, holds the owner's demo rulings (D295): buyer names, the
`assert_scrubbed` check, the deploy hold and the weekly refresh. Its docstring says what each proves.
Run: python3 scripts/demo-mirror-daily-photos-selftest.py"""
import atexit
import contextlib
import csv
import importlib.util
import io
import json
import os
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIRROR = "demo-assets/mirror/"
TEMP_ROOT = Path(tempfile.gettempdir()) / "banchi-test-runs"  # one temp root; each run owns one <pid>-<uuid> folder
MAX_AGE = 86400  # a crashed run's folder goes after a day; a newer sibling belongs to a parallel run
failures = []

# `scripts/serve.py down` stops the sweep watcher through its `.serve/match-sweep.json` pid record.
# The stub does the same, so a teardown that goes through `serve.py down` can stop the writer below.
SERVE_STUB = """import json, os, signal, sys
if sys.argv[1:] == ["down"]:
    try:
        os.kill(json.load(open(".serve/match-sweep.json"))["pid"], signal.SIGTERM)
    except (OSError, ValueError, KeyError):
        pass
"""
# The sweep watcher: started inside the tree, outlives `make`, rewrites its record by absolute path
# and recreates the folders above it, as `identify/sweep.py` does under the demo home.
WRITER = """import os, sys, time
p = sys.argv[1]
while True:
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write("{}")
    except OSError:
        pass
    time.sleep(0.005)
"""
# A watcher that traps SIGTERM, lives three more seconds, then writes its record once more.
SLOW_WRITER = """import os, signal, sys, time
p = sys.argv[1]
died = []
signal.signal(signal.SIGTERM, lambda *a: died.append(1))


def put():
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write("{}")
    except OSError:
        pass


while not died:
    put()
    time.sleep(0.005)
time.sleep(3)
put()
"""


def sweep(root):
    """The first request of a run: drop sibling run folders older than a day, keep the newer ones."""
    for d in root.glob("*-*") if root.is_dir() else []:
        if d.is_dir() and time.time() - d.stat().st_mtime > MAX_AGE:
            shutil.rmtree(d, ignore_errors=True)


def run_folder(root=TEMP_ROOT):
    sweep(root)
    d = root / ("%d-%s" % (os.getpid(), uuid.uuid4()))
    d.mkdir(parents=True)
    return d


RF = run_folder()  # every temp path below lives in it; teardown removes it
writers = []  # background processes the leak case starts


def stop_writers():
    for p in writers:
        p.kill()
        p.wait()
    writers.clear()


locked = []  # read-only folders the cases make; opened again before the run folder goes


def lock(path):
    """A folder neither git nor rmtree can remove: a file inside a read-only directory."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "f").write_text("1")
    path.chmod(0o555)
    locked.append(path)


def unlock_all():
    for p in locked:
        with contextlib.suppress(OSError):
            p.chmod(0o755)


atexit.register(shutil.rmtree, RF, ignore_errors=True)
atexit.register(stop_writers)  # last in, first out: the writers die before their folder goes, even if a case raises
atexit.register(unlock_all)


def git(cwd, *a, check=True):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd,
                          capture_output=True, text=True, check=check)


def ignored(path):
    d = tempfile.mkdtemp(dir=RF)
    try:
        git(d, "init", "-q", "-b", "main")
        shutil.copy(ROOT / ".gitignore", Path(d, ".gitignore"))
        p = Path(d, path)
        p.parent.mkdir(parents=True)
        p.write_bytes(b"x")
        return git(d, "check-ignore", "-q", path, check=False).returncode == 0
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case(name, ok, why):
    if not ok:
        failures.append(name)
        print("RED %s: %s" % (name, why))
    else:
        print("ok  " + name)


def chunk(cards):
    body = {"cards": {"%d/%d" % c: {"box": c[0], "index": c[1], "photo": "photos/ab/%d.jpg" % c[1]} for c in cards}}
    return json.dumps({"responses": {"/inventory": {"body": body}}, "wire": []})


def daily_run():
    """Drive run() in a throwaway origin and clone. Returns (outcome, seen)."""
    spec = importlib.util.spec_from_file_location("daily", ROOT / "scripts" / "demo-mirror-daily.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    base = Path(tempfile.mkdtemp(dir=RF))
    try:
        origin, clone = base / "origin.git", base / "clone"
        git(base, "init", "-q", "--bare", "-b", "main", str(origin))
        git(base, "clone", "-q", str(origin), str(clone))
        shutil.copy(ROOT / ".gitignore", clone / ".gitignore")
        b = clone / MIRROR / "bundle"
        b.mkdir(parents=True)
        (b / "chunk-0.json").write_text(chunk([(1, 1)]))
        ph = clone / MIRROR / "photos" / "1"
        ph.mkdir(parents=True)
        (ph / "1.jpg").write_bytes(b"x")
        git(clone, "add", "-f", ".")
        git(clone, "commit", "-q", "-m", "base")
        git(clone, "push", "-q", "origin", "HEAD:main")
        merge = base / "merge.sh"
        merge.write_text("#!/bin/sh\ntouch %s/merged\n" % base)
        merge.chmod(0o755)
        seen = {}
        real_sh = m.sh

        def sh(*cmd, cwd=None, check=True):
            if cmd[0] == "make":
                if cmd[1] == "demo-mirror":  # the rebuild: new chunk, new photographs on disk
                    (Path(cwd) / MIRROR / "bundle" / "chunk-0.json").write_text(chunk([(1, 1), (3, 1000), (3, 1001)]))
                    for i in (1000, 1001):
                        p = Path(cwd) / MIRROR / "photos" / "3" / ("%d.jpg" % i)
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_bytes(b"x")
                return ""
            if cmd[:2] == ("git", "push"):
                tree = real_sh("git", "ls-tree", "-r", "--name-only", "HEAD", cwd=cwd).split()
                want = ["%sphotos/3/%d.jpg" % (MIRROR, i) for i in (1000, 1001)]
                seen["missing"] = [f for f in want if f not in tree]
                return real_sh(*cmd, cwd=cwd)
            if cmd[0] == "gh":
                if "create" in cmd:
                    return "https://github.com/o/r/pull/1"
                if "headRefOid" in cmd:
                    return real_sh("git", "rev-parse", "HEAD", cwd=cwd)
                if "api" in cmd:
                    return "[[]]"
                return "OPEN"
            return real_sh(*cmd, cwd=cwd, check=check)

        m.sh, m.main_tree, m.clear_stale_pr, m.MERGE = sh, (lambda: clone), (lambda root: None), merge
        m.LOG = base / "daily.log"  # a run that logs must not write the owner's real log
        try:
            m.run(False)
            outcome = "ran"
        except m.Stop as e:
            outcome = "stopped: %s" % e
        seen["merged"] = (base / "merged").exists()
        return outcome, seen
    finally:
        shutil.rmtree(base, ignore_errors=True)


case("new mirror photo is not ignored", not ignored(MIRROR + "photos/3/1000.jpg"),
     ".gitignore matches demo-assets/mirror/photos/3/1000.jpg, so `git add` skips it")
case("photo store dirs stay ignored", ignored("photos/ab/x.jpg") and ignored("inventory/photos/ab/x.jpg"),
     "D172's photos/ directories are no longer ignored")
outcome, seen = daily_run()
shipped_without = seen.get("merged") and seen.get("missing")
case("daily run never ships a bundle whose photographs are not committed", not shipped_without,
     "merged with %s absent from the commit (run %s)" % (seen.get("missing"), outcome))


# The module's own waits, in seconds, which it reads when it runs. A case that cannot succeed (a folder
# nothing can remove) takes the whole wait, so the cases shorten the ones the module exposes.
FAST_WAITS = {"LSOF_TIMEOUT": 0.5, "REMOVE_RETRY_SECONDS": 0.5, "TERM_GRACE_SECONDS": 0.5}


def load_daily():
    spec = importlib.util.spec_from_file_location("daily", ROOT / "scripts" / "demo-mirror-daily.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for k, v in FAST_WAITS.items():
        if hasattr(m, k):
            setattr(m, k, v)
    return m


def step_unchanged(m, wt):
    pass


def step_stop(m, wt):
    raise m.Stop("make demo-mirror failed: boom")


def step_crash(m, wt):
    raise RuntimeError("boom")


def step_changed(m, wt):
    (wt / MIRROR).mkdir(parents=True, exist_ok=True)
    (wt / MIRROR / "a.json").write_text("{}")


def step_locked(inner):
    """Run `inner`, then leave a folder in the tree that nothing can remove."""
    def step(m, wt):
        lock(wt / "locked")
        inner(m, wt)
    return step


def step_slow_writer(m, wt):
    step_writer(m, wt, SLOW_WRITER)


def step_writer(m, wt, script=WRITER):
    target = wt / "demo" / "inventory" / "match-sweep.json"
    p = subprocess.Popen([sys.executable, "-c", script, str(target)], cwd=wt, start_new_session=True)
    writers.append(p)
    (wt / ".serve").mkdir(exist_ok=True)
    (wt / ".serve" / "match-sweep.json").write_text(json.dumps({"pid": p.pid}))
    end = time.time() + 10
    while not target.exists():
        if time.time() > end:
            raise RuntimeError("fixture: the writer never started")
        time.sleep(0.01)


def drive(m, origin, merge, name, step, setup=None):
    """Run m.run() over a fresh clone, `step` standing in for `make demo-mirror`, `setup(clone)`
    laying out what an earlier run left. Returns (outcome, what is left behind, the clone)."""
    clone = RF / name
    git(RF, "clone", "-q", str(origin), str(clone))
    if setup:
        setup(clone)
    real_sh = m.sh

    def sh(*cmd, cwd=None, check=True):
        if cmd[0] == "make":
            if cmd[1] == "demo-mirror":
                step(m, Path(cwd))
            return ""
        if cmd[0] == "gh":
            if "create" in cmd:
                return "https://github.com/o/r/pull/1"
            if "api" in cmd:
                return "[[]]"
            if "headRefOid" in cmd:
                return real_sh("git", "rev-parse", "HEAD", cwd=cwd)
            return "OPEN"
        if cmd[:2] == ("git", "commit"):
            return real_sh("git", "-c", "user.name=t", "-c", "user.email=t@t", *cmd[1:], cwd=cwd)
        return real_sh(*cmd, cwd=cwd, check=check)

    def clear_stale_pr(root):  # no gh here; keep the real one's last step, so a branch a run left does not reject the next push
        real_sh("git", "push", "origin", "--delete", m.BRANCH, cwd=root, check=False)

    patch = {"sh": sh, "main_tree": lambda: clone, "clear_stale_pr": clear_stale_pr, "MERGE": merge,
             "LOG": RF / (name + ".log")}
    saved = {k: getattr(m, k) for k in patch}
    for k, v in patch.items():
        setattr(m, k, v)
    try:
        outcome = m.run(False)
    except Exception as e:
        outcome = e
    finally:
        for k, v in saved.items():
            setattr(m, k, v)
    wts = clone / ".claude" / "worktrees"
    if writers:  # a writer is alive: give it time to bring a removed folder back
        end = time.time() + 1.0
        while time.time() < end and not list(wts.glob("demo-mirror-daily-*")):
            time.sleep(0.01)
    left = ["folder %s is still on disk" % p.name for p in sorted(wts.glob("demo-mirror-daily-*"))]
    for line in git(clone, "worktree", "list", "--porcelain").stdout.splitlines():
        if "demo-mirror-daily" in line:
            left.append("git still registers it: " + line)
    left += ["admin entry .git/worktrees/%s is left" % p.name for p in sorted((clone / ".git" / "worktrees").glob("*"))]
    return outcome, left, clone


# the run-folder sweep (test-temp-standard): an old sibling goes, a new one stays
siblings = RF / "siblings"
old, new = siblings / "1-old", siblings / "2-new"
old.mkdir(parents=True)
new.mkdir()
os.utime(old, (time.time() - 2 * MAX_AGE,) * 2)
sweep(siblings)
case("run-folder sweep: old sibling goes, new one stays", not old.exists() and new.exists(),
     "old exists=%s, new exists=%s" % (old.exists(), new.exists()))

daily = load_daily()
origin, seed = RF / "origin.git", RF / "seed"
git(RF, "init", "-q", "--bare", "-b", "main", str(origin))
git(RF, "clone", "-q", str(origin), str(seed))
(seed / "scripts").mkdir()
(seed / "scripts" / "serve.py").write_text(SERVE_STUB)
git(seed, "add", ".")
git(seed, "commit", "-q", "-m", "base")
git(seed, "push", "-q", "origin", "HEAD:main")
merge_fake = RF / "merge.sh"
merge_fake.write_text("#!/bin/sh\nexit 0\n")
merge_fake.chmod(0o755)


def returned(prefix):
    return lambda o: isinstance(o, str) and o.startswith(prefix)


for name, step, ok, want in (
    ("unchanged result", step_unchanged, returned("unchanged"), "an 'unchanged' result"),
    ("Stop mid-run", step_stop, lambda o: isinstance(o, daily.Stop), "a Stop"),
    ("unexpected exception", step_crash, lambda o: isinstance(o, RuntimeError), "a RuntimeError"),
    ("merged", step_changed, returned("merged PR 1"), "a 'merged PR 1' result"),
    ("background writer left in the tree", step_writer, returned("unchanged"), "an 'unchanged' result"),
):
    outcome, left, _ = drive(daily, origin, merge_fake, name.replace(" ", "-"), step)
    stop_writers()
    if not ok(outcome):
        left.insert(0, "fixture: run() ended %r, wanted %s" % (outcome, want))
    case("worktree gone after run(): " + name, not left, "; ".join(left))

# The sweep at the start of run(): leftovers of runs that never reached their finally.
STALE = ("demo-mirror-daily-1000000001", "demo-mirror-daily-1000000002", "demo-mirror-daily-1000000003")
KEEP = {  # names the sweep must not touch, under .claude/worktrees: the file inside a folder, or None for a file
    "demo-mirror-daily-notes": "keep.txt",
    "demo-mirror-daily-12.log": None,
    "agent-x": "keep.txt",
    "notes.txt": None,
}


def stale_setup(clone):
    wts = clone / ".claude" / "worktrees"
    wts.mkdir(parents=True)
    git(clone, "worktree", "add", "-q", "--detach", str(wts / STALE[0]), "HEAD")  # a registered worktree
    (wts / STALE[0] / "untracked.txt").write_text("1")
    whole = wts / STALE[1]  # a whole tree git no longer registers
    (whole / "node_modules" / "x").mkdir(parents=True)
    (whole / "node_modules" / "x" / "y.js").write_text("1")
    (whole / ".git").write_text("gitdir: /nonexistent/worktrees/gone\n")
    (whole / "README").write_text("1")
    (wts / STALE[2] / "demo" / "inventory").mkdir(parents=True)  # the stub a late writer leaves
    (wts / STALE[2] / "demo" / "inventory" / "x.json").write_text("{}")
    for n, inner in KEEP.items():
        if inner:
            (wts / n).mkdir()
            (wts / n / inner).write_text("keep")
        else:
            (wts / n).write_text("keep")
    (wts / "agent-x" / ".git").write_text("gitdir: /nonexistent/worktrees/agent-x\n")


outcome, _, clone = drive(daily, origin, merge_fake, "sweep", step_unchanged, stale_setup)
wts = clone / ".claude" / "worktrees"
gone = ["%s is still on disk" % n for n in STALE if os.path.lexists(wts / n)]
gone += ["git still registers it: " + line for line in git(clone, "worktree", "list", "--porcelain").stdout.splitlines()
         if "demo-mirror-daily" in line]
gone += ["admin entry .git/worktrees/%s is left" % p.name for p in sorted((clone / ".git" / "worktrees").glob("*"))]
if not returned("unchanged")(outcome):
    gone.insert(0, "fixture: run() ended %r, wanted an 'unchanged' result" % (outcome,))
case("sweep: registered, unregistered and stub leftovers are gone after run()", not gone, "; ".join(gone))
hurt = []
for n, inner in KEEP.items():
    path = wts / n / inner if inner else wts / n
    if not path.is_file() or path.read_text() != "keep":
        hurt.append("%s was removed or changed" % n)
if not (wts / "agent-x" / ".git").is_file():
    hurt.append("agent-x lost its .git file")
case("sweep: names that do not match are untouched", not hurt, "; ".join(hurt))


def link_setup(clone):
    """A stale-looking name that is a symlink to another linked worktree, which has its own servers."""
    outside = RF / "outside"
    git(clone, "worktree", "add", "-q", "--detach", str(outside), "HEAD")
    (outside / "keep.txt").write_text("keep")
    (outside / "scripts" / "serve.py").write_text("open(%r, 'w').write('1')\n" % str(RF / "down-ran"))  # marker if `serve.py down` runs here
    (clone / ".claude" / "worktrees").mkdir(parents=True)
    (clone / ".claude" / "worktrees" / "demo-mirror-daily-1000000004").symlink_to(outside, target_is_directory=True)


outcome, _, clone = drive(daily, origin, merge_fake, "link", step_unchanged, link_setup)
outside = RF / "outside"
hurt = []
if not outside.is_dir():
    hurt.append("the link's target folder was deleted")
elif not (outside / "keep.txt").is_file():
    hurt.append("files in the link's target were deleted")
if (RF / "down-ran").exists():
    hurt.append("`serve.py down` ran in the link's target (its servers were stopped)")
if str(outside.resolve()) not in git(clone, "worktree", "list", "--porcelain").stdout:
    hurt.append("git no longer registers the link's target worktree")
case("sweep: a symlink named like a stale folder is not followed", not hurt,
     "%s (run() ended %r)" % ("; ".join(hurt), outcome))


# A tree that cannot be removed must not rewrite what the run did. The verdict is what run() returns
# (main logs it as it stands) or the Stop it raises (main logs "stopped, nothing published: <reason>").
def names_removal(text):
    return "demo-mirror-daily-" in text or "remov" in text.lower()


for name, inner, prefix in (("merged", step_changed, "merged PR 1"), ("unchanged", step_unchanged, "unchanged")):
    outcome, _, _ = drive(daily, origin, merge_fake, "locked-" + name, step_locked(inner))
    case("removal failure: a %s run still returns its verdict, with the failure named" % name,
         isinstance(outcome, str) and outcome.startswith(prefix) and names_removal(outcome[len(prefix):]),
         "run() ended %r" % (outcome,))
outcome, _, _ = drive(daily, origin, merge_fake, "locked-stop", step_locked(step_stop))
case("removal failure: a run that already stopped keeps its own reason", "boom" in str(outcome),
     "run() ended %r" % (outcome,))


def missing_setup(clone):
    """The previous run's tree was deleted by hand: git still registers it, and holds the branch."""
    gone = clone / ".claude" / "worktrees" / "demo-mirror-daily-1000000005"
    git(clone, "worktree", "add", "-q", "-B", daily.BRANCH, str(gone), "HEAD")
    shutil.rmtree(gone)


outcome, _, clone = drive(daily, origin, merge_fake, "missing", step_unchanged, missing_setup)
registered = [line for line in git(clone, "worktree", "list", "--porcelain").stdout.splitlines()
              if "demo-mirror-daily" in line]
case("a registered tree deleted by hand does not stop the next run",
     returned("unchanged")(outcome) and not registered,
     "run() ended %r; still registered: %s" % (outcome, registered))


def stuck_setup(clone):
    wts = clone / ".claude" / "worktrees"
    lock(wts / "demo-mirror-daily-1000000011")  # cannot be removed
    for n in ("demo-mirror-daily-1000000012", "demo-mirror-daily-1000000013"):
        (wts / n).mkdir()
        (wts / n / "x.json").write_text("{}")


outcome, _, clone = drive(daily, origin, merge_fake, "stuck", step_unchanged, stuck_setup)
wts = clone / ".claude" / "worktrees"
untried = [n for n in ("demo-mirror-daily-1000000012", "demo-mirror-daily-1000000013") if (wts / n).exists()]
logged = (RF / "stuck.log").read_text() if (RF / "stuck.log").exists() else ""
case("sweep: a leftover that cannot be removed is logged, the run goes on, the others are tried",
     returned("unchanged")(outcome) and not untried and "demo-mirror-daily-1000000011" in logged + str(outcome),
     "run() ended %r; not removed: %s; log: %r" % (outcome, untried, logged))


def slow_setup(clone):
    wts = clone / ".claude" / "worktrees"
    wts.mkdir(parents=True)
    (wts / "demo-mirror-daily-1.bak").mkdir()
    (wts / "demo-mirror-daily-1.bak" / "keep.txt").write_text("keep")
    (wts / "demo-mirror-daily-x").write_text("keep")


outcome, _, clone = drive(daily, origin, merge_fake, "slow", step_slow_writer, slow_setup)
wts = clone / ".claude" / "worktrees"
with contextlib.suppress(subprocess.TimeoutExpired):
    writers[-1].wait(timeout=15)  # the worker writes its record once more, three seconds after SIGTERM
back = ["folder %s came back after run() returned" % p.name for p in sorted(wts.glob("demo-mirror-daily-*"))
        if p.name not in ("demo-mirror-daily-1.bak", "demo-mirror-daily-x")]
if not ((wts / "demo-mirror-daily-1.bak" / "keep.txt").is_file() and (wts / "demo-mirror-daily-x").is_file()):
    back.append("a name that does not match the pattern was removed")
case("a worker that outlives SIGTERM does not bring the folder back", not back and returned("unchanged")(outcome),
     "run() ended %r; %s" % (outcome, "; ".join(back)))


# drop_tree finds what stands in a tree with `lsof`. It must never kill a process that is running the job,
# must leave a session alone when the janitor says one is still there, and must not hang or crash on lsof.
def fake_here(rc):
    """A stand-in for the module's HERE whose neighbouring janitor.py exits with `rc`."""
    d = RF / ("fakejan-%d" % rc)
    (d / "scripts").mkdir(parents=True, exist_ok=True)
    (d / "scripts" / "janitor.py").write_text("import sys\nsys.exit(%d)\n" % rc)
    return d / "scripts" / "demo-mirror-daily.py"


def leaked_tree(name):
    """A clone with one leftover folder in it. Returns (clone, folder)."""
    clone = RF / name
    git(RF, "clone", "-q", str(origin), str(clone))
    leaked = clone / ".claude" / "worktrees" / "demo-mirror-daily-1000000099"
    leaked.mkdir(parents=True)
    (leaked / "x.json").write_text("{}")
    return clone, leaked


def standing_in(folder):
    """A process whose working directory is `folder`, which only a kill ends."""
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], cwd=folder, start_new_session=True)
    writers.append(p)
    return p


def bin_dir(name, lsof=None):
    """A PATH holding only git, plus an lsof that runs `lsof` (a python source) when given."""
    d = RF / name
    d.mkdir()
    (d / "git").symlink_to(shutil.which("git"))
    if lsof:
        (d / "lsof").write_text("#!%s\n%s\n" % (sys.executable, lsof))
        (d / "lsof").chmod(0o755)
    return d


@contextlib.contextmanager
def path_only(d):
    saved = os.environ["PATH"]
    os.environ["PATH"] = str(d)
    try:
        yield
    finally:
        os.environ["PATH"] = saved


HOLDER = """import subprocess, sys
sys.exit(subprocess.call([sys.executable, "-c", sys.argv[2]] + sys.argv[3:], cwd=sys.argv[1]))
"""
DROPPER = """import importlib.util, json, pathlib, sys
spec = importlib.util.spec_from_file_location("daily", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
for k, v in json.loads(sys.argv[6]).items():
    if hasattr(m, k):
        setattr(m, k, v)
m.HERE = pathlib.Path(sys.argv[5])
open(sys.argv[4], "w").write(repr(m.drop_tree(pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]))))
"""

if shutil.which("lsof"):
    # The job's parent stands in the leaked folder (a shell the owner left there). The dropper is its child.
    clone, leaked = leaked_tree("ancestor")
    result = RF / "ancestor.result"
    stuck = standing_in(leaked)
    parent = subprocess.Popen([sys.executable, "-c", HOLDER, str(RF), DROPPER, str(ROOT / "scripts" / "demo-mirror-daily.py"),
                               str(clone), str(leaked), str(result), str(fake_here(0)), json.dumps(FAST_WAITS)],
                              cwd=leaked, start_new_session=True)
    writers.append(parent)
    code = parent.wait(timeout=120)
    with contextlib.suppress(subprocess.TimeoutExpired):
        stuck.wait(timeout=5)
    bad = []
    if code != 0:
        bad.append("the job's parent, standing in the folder, ended with %d (SIGKILL is -9)" % code)
    if stuck.poll() is None:
        bad.append("a stuck worker in the folder was left alive")
    if leaked.exists():
        bad.append("the folder is still there")
    case("drop_tree kills a stuck worker but never an ancestor of the job", not bad,
         "; ".join(bad) + " (drop_tree returned %s)" % (result.read_text() if result.exists() else "nothing"))

    clone, leaked = leaked_tree("session")
    stuck = standing_in(leaked)
    daily.HERE, was = fake_here(3), daily.HERE  # the janitor reports a session still in the tree
    try:
        text = daily.drop_tree(clone, leaked)
    except Exception as e:
        text = e
    finally:
        daily.HERE = was
    case("drop_tree leaves a worker alone when the janitor exits 3 (a session is still there)",
         stuck.poll() is None and isinstance(text, str), "worker alive=%s, drop_tree returned %r" % (stuck.poll() is None, text))
    stop_writers()

    # A hung lsof: cwd_pids gives up after daily.LSOF_TIMEOUT (a module constant, read at call time) and answers [].
    daily.LSOF_TIMEOUT, was_timeout = 0.5, getattr(daily, "LSOF_TIMEOUT", None)
    hung = bin_dir("bin-hung", "import time\ntime.sleep(6)")
    clone, leaked = leaked_tree("hung")
    with path_only(hung):
        t0 = time.time()
        try:
            got = daily.cwd_pids(leaked)
        except Exception as e:
            got = e
        took = time.time() - t0
    case("cwd_pids gives up on a hung lsof and answers no pids", got == [] and took < 3,
         "answered %r after %.1f s with LSOF_TIMEOUT=0.5" % (got, took))
    lock(leaked / "locked")
    daily.HERE, was = fake_here(0), daily.HERE
    with path_only(hung):
        t0 = time.time()
        try:
            text = daily.drop_tree(clone, leaked)
        except Exception as e:
            text = e
        took = time.time() - t0
    daily.HERE = was
    case("drop_tree with a hung lsof still returns its failure text, in bounded time",
         isinstance(text, str) and text.startswith("could not remove") and took < 12,
         "returned %r after %.1f s" % (text, took))
    # no lsof at all
    clone, leaked = leaked_tree("nolsof")
    daily.HERE, was = fake_here(0), daily.HERE
    with path_only(bin_dir("bin-none")):
        try:
            got, text = daily.cwd_pids(leaked), daily.drop_tree(clone, leaked)
        except Exception as e:
            got = text = e
    daily.HERE = was
    case("a missing lsof does not crash drop_tree", got == [] and text == "", "cwd_pids %r, drop_tree %r" % (got, text))
    if was_timeout is not None:
        daily.LSOF_TIMEOUT = was_timeout
else:
    print("skip the lsof cases: no lsof on this machine")


def policy_rulings():
    """The owner's demo rulings (D295), each red before its build. Nothing here touches the real HOME,
    PATH, launchd or store.

      names    `demo-mirror.py`'s `build()` stores "Jordan Miller" as "Jordan M." and keeps a one-word
               name. Run through `build()` over a tiny real store, so no function name is fixed: only
               the stored buyer and the shipping export are read back.
      check    `assert_scrubbed()` accepts that form, still refuses a surname or an address-shaped
               value, and never prints a value it refused.
      hold     `scripts/demo-hold.py --chunk PATH` is what the workflow runs. It compares the chunk's
               `wire` with `demo-record.py`'s `wire_digest()` of this tree, exits 0 either way, appends
               `publish=true` or `publish=false` to the file `$GITHUB_OUTPUT` names, and prints a
               `::notice::` line naming both digests when it holds. A chunk with no `wire` holds.
      cadence  `demo-mirror-daily.py`'s `agent()` installs a job that fires weekly:
               `StartCalendarInterval` is ONE dict with an int `Weekday` (0 to 7), `Hour` and `Minute`.
               Run against a fake HOME and a fake `launchctl` that is the only one on PATH.

    The refusal cases in `check` pass on the old code too: they pin the check shut while the name
    rule relaxes. The accepted-form case is the one that is red there.
    """
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    address = "123 Demo Way"
    modules, built, unique = {}, [], [0]

    def fresh(label):
        unique[0] += 1
        d = RF / ("policy-%s-%d" % (label, unique[0]))
        d.mkdir(parents=True)
        return d

    def need(condition, why):
        if not condition:
            raise AssertionError(why)

    def policy(name, fn):
        try:
            fn()
        except AssertionError as exc:
            case(name, False, str(exc))
        except Exception as exc:  # a missing function or script is a red case, not a dead run
            case(name, False, "crashed: %s: %s" % (type(exc).__name__, exc))
        else:
            case(name, True, "")

    def load(rel):
        if rel not in modules:
            spec = importlib.util.spec_from_file_location("policy_" + Path(rel).stem.replace("-", "_"), ROOT / rel)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            modules[rel] = module
        return modules[rel]

    @contextlib.contextmanager
    def env(**values):
        old = {k: os.environ.get(k) for k in values}
        os.environ.update(values)
        try:
            yield
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    # ---- names: `build()` over three orders, no photographs, read back once
    def build_once():
        if built:
            if isinstance(built[0], Exception):
                raise built[0]
            return built[0]
        try:
            demo_mirror = load("scripts/demo-mirror.py")
            from store import Store
            from store.orders import OrderLine, OrderRecord

            base = fresh("names")
            with env(BANCHI_HOME=str(base / "real")), Store().write() as snap:
                snap.ledger.ingest([
                    OrderRecord(source="tcg", number="1", placed_at="2026-01-01", status="Ready to Ship",
                                buyer="Jordan Miller", lines=[OrderLine(sku="1", quantity=1)]),
                    OrderRecord(source="tcg", number="2", placed_at="2026-01-02", status="Ready to Ship",
                                buyer="Priya", lines=[OrderLine(sku="2", quantity=1)]),
                    OrderRecord(source="tcg", number="3", placed_at="2026-01-03", status="Shipped",
                                buyer=None, lines=[OrderLine(sku="3", quantity=1)]),
                    OrderRecord(source="tcg", number="4", placed_at="2026-01-04", status="Ready to Ship",
                                buyer="Zoë Ångström", lines=[OrderLine(sku="4", quantity=1)]),
                    OrderRecord(source="tcg", number="5", placed_at="2026-01-05", status="Ready to Ship",
                                buyer="Mary Jane Watson", lines=[OrderLine(sku="5", quantity=1)]),
                ])
            snapshot = base / "snapshot"
            snapshot.mkdir()
            shutil.copytree(base / "real" / "inventory", snapshot / "inventory")
            (snapshot / "SOURCE").write_text(str(base / "no-source") + "\n")
            demo_mirror.SNAPSHOT = snapshot
            home = base / "home"
            with env(BANCHI_HOME=str(home)):
                with contextlib.redirect_stdout(io.StringIO()):
                    demo_mirror.build(home, 1)
                buyers = {r.number: r.buyer for r in Store().read().ledger.orders.values()}
            with (home / "shipping-export.csv").open(newline="", encoding="utf-8") as handle:
                shipping = {row["Order #"]: row for row in csv.DictReader(handle)}
            built.append({"buyers": buyers, "shipping": shipping, "home": home})
        except Exception as exc:
            built.append(exc)
            raise
        return built[0]

    def names_full_name_to_initial():
        got = build_once()["buyers"].get("1")
        need(got == "Jordan M.", "buyer 'Jordan Miller' is stored as %r, want 'Jordan M.'" % got)

    def names_one_word_kept():
        got = build_once()["buyers"].get("2")
        need(got == "Priya", "buyer 'Priya' is stored as %r, want 'Priya'" % got)
        need(build_once()["buyers"].get("3") is None, "an order with no buyer must stay without one")

    def names_shipping_export():
        rows = build_once()["shipping"]
        jordan, priya = rows.get("1"), rows.get("2")
        need(jordan is not None and priya is not None, "shipping export lacks a Ready to Ship order")
        need((jordan["FirstName"], jordan["LastName"]) == ("Jordan", "M."),
             "shipping name is %r %r, want 'Jordan' 'M.'" % (jordan["FirstName"], jordan["LastName"]))
        need((priya["FirstName"], priya["LastName"]) == ("Priya", ""),
             "shipping name is %r %r, want 'Priya' ''" % (priya["FirstName"], priya["LastName"]))
        for row in (jordan, priya):
            need(row["Address1"] == address and not row["Address2"]
                 and not (row["City"] or row["State"] or row["PostalCode"]),
                 "an address field is not blank or '123 Demo Way'")
        text = (build_once()["home"] / "shipping-export.csv").read_text(encoding="utf-8")
        need("Miller" not in text, "the shipping export still holds a full surname")

    def names_accented_and_long_names():
        # An accented letter and a three-word name each come out as a short name with no surname in it.
        # The output check below then proves the check takes the scrub's own output (an accented initial).
        got, text = build_once()["buyers"], (build_once()["home"] / "shipping-export.csv").read_text(encoding="utf-8")
        need((got.get("4") or "").startswith("Zoë ") and "ngström" not in (got.get("4") or ""),
             "buyer 'Zoë Ångström' is stored as %r, want 'Zoë' and an initial" % got.get("4"))
        need((got.get("5") or "").startswith("Mary ") and "Watson" not in (got.get("5") or ""),
             "buyer 'Mary Jane Watson' is stored as %r, want 'Mary' and no 'Watson'" % got.get("5"))
        need("ngström" not in text and "Watson" not in text, "the shipping export still holds a full surname")

    def names_output_passes_the_check():
        # build()'s own output must satisfy the one check, whatever form the names take.
        buyers = [b for b in build_once()["buyers"].values() if b]
        bundle = fresh("chain") / "bundle.json"
        bundle.write_text(json.dumps({"responses": {"/orders": {"body": {"orders": [{"buyer": b} for b in buyers]}}}}))
        load("scripts/demo-mirror.py").assert_scrubbed(bundle, build_once()["home"] / "shipping-export.csv")

    # ---- check: `assert_scrubbed`
    header = ["Order #", "FirstName", "LastName", "Address1", "Address2", "City", "State", "PostalCode", "Country"]

    def ship(first, last, a1=address, a2="", city="", state="", zip_=""):
        return ["1", first, last, a1, a2, city, state, zip_, "US"]

    def scrubbed(bundle, rows=()):
        d = fresh("check")
        (d / "bundle.json").write_text(json.dumps(bundle))
        with (d / "shipping.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        try:
            load("scripts/demo-mirror.py").assert_scrubbed(d / "bundle.json", d / "shipping.csv")
        except (AssertionError, SystemExit) as exc:
            return False, str(exc)
        return True, ""

    def orders_bundle(**fields):
        return {"responses": {"/orders": {"body": {"orders": [dict(fields)]}}}}

    def check_accepts_new_form():
        # Two-word and one-word buyers under both buyer keys, an allowed address, null and blank
        # fields, and shipping rows with and without a last initial.
        bundle = {"responses": {"/orders": {"body": {"orders": [
            {"buyer": "Jordan M.", "address1": address, "address2": ""},
            {"buyerName": "Priya", "address": None},
            {"buyer": None},
        ]}}}}
        accepted, message = scrubbed(bundle, [ship("Jordan", "M."), ship("Priya", "")])
        need(accepted, "assert_scrubbed refuses first name + last initial: %s" % message)

    def check_refuses_surname():
        # Each value names more than a first name and a last initial. Each is refused under every
        # buyer key, nested at depth, and in the shipping export. The distinct surname proves the
        # message never echoes what it refused.
        accepted, leaked = [], []
        for value in ("Jordan Quimby", "Jordan Qu.", "Jordan M. Quimby", "Quimby Jordan"):
            for key in ("buyer", "buyerName", "Buyer"):
                ok, message = scrubbed(orders_bundle(**{key: value}))
                if ok:
                    accepted.append("%s=%r" % (key, value))
                elif value.split()[-1] in message or "Quimby" in message:
                    leaked.append(value)
            ok, _ = scrubbed({"responses": {"/x": {"body": {"rows": [[{"deep": {"buyer": value}}]]}}}})
            if ok:
                accepted.append("nested %r" % value)
        ok, message = scrubbed({"responses": {}}, [ship("Jordan", "Quimby")])
        if ok:
            accepted.append("shipping LastName 'Quimby'")
        elif "Quimby" in message:
            leaked.append("shipping LastName")
        ok, _ = scrubbed({"responses": {}}, [ship("Jordan Quimby", "M.")])
        if ok:
            accepted.append("shipping FirstName 'Jordan Quimby'")
        need(not accepted, "assert_scrubbed accepts a surname: %s" % "; ".join(accepted))
        need(not leaked, "the failure message echoes a refused value: %s" % "; ".join(leaked))

    def check_refuses_address():
        street = "4471 Zephyr Lane"
        accepted, leaked = [], []
        for key in ("address", "address1", "address2", "street", "Address1"):
            ok, message = scrubbed(orders_bundle(**{key: street}))
            if ok:
                accepted.append("bundle %s" % key)
            elif "Zephyr" in message:
                leaked.append(key)
        ok, _ = scrubbed(orders_bundle(buyer=street))
        if ok:
            accepted.append("an address in the buyer field")
        rows = {
            "shipping Address1": ship("Jordan", "M.", a1=street),
            "shipping Address2": ship("Jordan", "M.", a2="Apt 4"),
            "shipping City": ship("Jordan", "M.", city="Austin"),
            "shipping State": ship("Jordan", "M.", state="TX"),
            "shipping PostalCode": ship("Jordan", "M.", zip_="78701"),
        }
        for label, row in rows.items():
            ok, message = scrubbed({"responses": {}}, [row])
            if ok:
                accepted.append(label)
            elif "Zephyr" in message or "Austin" in message or "78701" in message:
                leaked.append(label)
        need(not accepted, "assert_scrubbed accepts an address-shaped value: %s" % "; ".join(accepted))
        need(not leaked, "the failure message echoes a refused value: %s" % "; ".join(leaked))

    # ---- hold: the script the workflow runs
    def hold(chunk):
        """Returns (returncode, stdout, the GITHUB_OUTPUT file as a dict)."""
        script = ROOT / "scripts" / "demo-hold.py"
        need(script.is_file(), "scripts/demo-hold.py does not exist")
        d = fresh("hold")
        (d / "chunk-0.json").write_text(json.dumps(chunk))
        out = d / "github-output"
        out.write_text("")
        # An explicit GITHUB_OUTPUT: CI sets one, and an inherited path would write into the real step.
        run = subprocess.run([sys.executable, str(script), "--chunk", str(d / "chunk-0.json")],
                             env=dict(os.environ, GITHUB_OUTPUT=str(out)), capture_output=True, text=True,
                             timeout=120)
        pairs = dict(line.split("=", 1) for line in out.read_text().splitlines() if "=" in line)
        return run.returncode, run.stdout, pairs

    def tree_digest():
        return load("scripts/demo-record.py").wire_digest()

    def hold_publishes_on_match():
        code, stdout, out = hold({"responses": {}, "wire": tree_digest()})
        need(code == 0, "exit %s on a match, want 0" % code)
        need(out.get("publish") == "true", "GITHUB_OUTPUT says publish=%r on a match, want 'true'" % out.get("publish"))
        need("::notice::" not in stdout, "a match printed a hold notice")

    def hold_skips_on_mismatch():
        recorded = "0000000000000000" if tree_digest() != "0000000000000000" else "ffffffffffffffff"
        code, stdout, out = hold({"responses": {}, "wire": recorded})
        need(code == 0, "exit %s on a mismatch, want 0 (a hold is not a failure)" % code)
        need(out.get("publish") == "false",
             "GITHUB_OUTPUT says publish=%r on a mismatch, want 'false'" % out.get("publish"))
        need("::notice::" in stdout, "a hold printed no ::notice:: line")
        need(recorded in stdout and tree_digest() in stdout,
             "the hold notice must name the recorded digest and the tree's digest")

    def hold_skips_without_a_recorded_digest():
        # A recording that names no wire cannot be shown to cover this tree: unknown is not clear.
        for label, chunk in (("no wire key", {"responses": {}}), ("empty wire", {"responses": {}, "wire": ""})):
            code, _stdout, out = hold(chunk)
            need(code == 0 and out.get("publish") == "false",
                 "%s: exit %s, publish=%r, want exit 0 and publish='false'" % (label, code, out.get("publish")))

    # ---- cadence: `agent()` against a fake HOME and a fake launchctl
    def cadence_is_weekly():
        home, fake_bin, repo = fresh("home"), fresh("bin"), fresh("repo")
        launchctl = fake_bin / "launchctl"
        launchctl.write_text("#!/bin/sh\nexit 0\n")
        launchctl.chmod(launchctl.stat().st_mode | stat.S_IXUSR)
        (repo / ".git").mkdir()
        (repo / "scripts").mkdir()
        with env(HOME=str(home), PATH=str(fake_bin)):
            need(shutil.which("launchctl") == str(launchctl), "isolation failed: launchctl is not the fake one")
            job = load("scripts/demo-mirror-daily.py")
            job.HERE = repo / "scripts" / "demo-mirror-daily.py"
            with contextlib.redirect_stdout(io.StringIO()):
                code = job.agent(False)
            plist = home / "Library" / "LaunchAgents" / (job.LABEL + ".plist")
            need(code == 0, "agent() returned %s against a fake launchctl" % code)
            need(plist.is_file(), "agent() wrote no job file")
            payload = plistlib.loads(plist.read_bytes())
        when = payload.get("StartCalendarInterval")
        need(isinstance(when, dict), "StartCalendarInterval is %r, want one dict" % (when,))
        weekday = when.get("Weekday")
        need(isinstance(weekday, int) and not isinstance(weekday, bool) and 0 <= weekday <= 7,
             "no Weekday in %r: the job fires daily, want weekly" % (when,))
        need(isinstance(when.get("Hour"), int) and isinstance(when.get("Minute"), int),
             "%r lacks an Hour or a Minute" % (when,))
        need("StartInterval" not in payload, "a StartInterval beside the calendar entry would fire more often")

    policy("names: a full name is stored as first name + last initial", names_full_name_to_initial)
    policy("names: a one-word name is kept and a missing buyer stays missing", names_one_word_kept)
    policy("names: the shipping export carries the short name and a blank-or-demo address", names_shipping_export)
    policy("names: an accented name and a three-word name lose their surname", names_accented_and_long_names)
    policy("names: build() output passes assert_scrubbed", names_output_passes_the_check)
    policy("check: assert_scrubbed accepts first name + last initial", check_accepts_new_form)
    policy("check: assert_scrubbed refuses a surname and never echoes it", check_refuses_surname)
    policy("check: assert_scrubbed refuses an address-shaped value and never echoes it", check_refuses_address)
    policy("hold: a matching digest publishes", hold_publishes_on_match)
    policy("hold: a digest mismatch skips, exits 0, prints a notice", hold_skips_on_mismatch)
    policy("hold: no recorded digest skips", hold_skips_without_a_recorded_digest)
    policy("cadence: the installed job fires weekly", cadence_is_weekly)


policy_rulings()
sys.exit(1 if failures else 0)
