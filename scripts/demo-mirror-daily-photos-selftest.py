#!/usr/bin/env python3
# Protects: The daily demo mirror never publishes a bundle that names a card whose photograph it did not commit, and removes its throwaway worktree on every exit path.
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
Run: python3 scripts/demo-mirror-daily-photos-selftest.py"""
import atexit
import contextlib
import importlib.util
import json
import os
import shutil
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


def load_daily():
    spec = importlib.util.spec_from_file_location("daily", ROOT / "scripts" / "demo-mirror-daily.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
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
sys.exit(1 if failures else 0)
