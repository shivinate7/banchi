#!/usr/bin/env python3
"""Daily demo refresh (D295, docs/specs/demo.md §13). Owner's Mac, main tree only.

Cuts a throwaway worktree from fresh origin/main, runs `make demo-mirror` there, and
publishes the result ONLY if `demo-assets/mirror/` changed and the diff touches nothing
else. Any error: publish nothing, log why. One log line per run.

  demo-mirror-daily.py [--dry-run]   stop before push, print what would go out
  demo-mirror-daily.py --agent [--remove]   install / remove the daily launchd job
  demo-mirror-daily.py --selftest    the fence goes red, then green

The fence is what makes the standing auto-merge grant safe: `fence()` refuses any path
outside `demo-assets/mirror/`, checked on the local diff and again on the PR's own diff.
"""
import argparse
import datetime
import os
import plistlib
import posixpath
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ALLOWED = "demo-assets/mirror/"
BRANCH = "demo/mirror-refresh"
LABEL = "com.banchi.demo-mirror-daily"
LOG = Path.home() / ".pkmnscan" / "demo-mirror-daily.log"
MERGE = Path.home() / ".claude" / "bin" / "merge"
SOURCE = Path.home() / "Developer" / "pkmnscan"
HERE = Path(__file__).resolve()


class Stop(Exception):
    pass


def fence(paths):
    """Refuse a diff that touches anything outside demo-assets/mirror/."""
    bad = [p for p in paths if not posixpath.normpath(p).startswith(ALLOWED)]
    if bad:
        raise Stop("fence: %d path(s) outside %s, first: %s" % (len(bad), ALLOWED, bad[0]))


def sh(*cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise Stop("%s failed: %s" % (" ".join(cmd[:3]), (r.stderr or r.stdout).strip()[-300:]))
    return r.stdout.strip()


def log(verdict):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write("%s %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), verdict))
    print(verdict)


def main_tree():
    common = sh("git", "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=HERE.parent)
    return Path(common).parent


def run(dry):
    root = main_tree()
    wt = root / ".claude" / "worktrees" / ("demo-mirror-daily-%d" % time.time())
    sh("git", "fetch", "-q", "origin", "main", cwd=root)
    sh("git", "worktree", "add", "-q", "-B", BRANCH, str(wt), "origin/main", cwd=root)
    try:
        sh("make", "worktree-setup", cwd=wt)
        t0 = time.time()
        sh("make", "demo-mirror", "SOURCE=%s" % SOURCE, cwd=wt)
        took = int(time.time() - t0)
        if not sh("git", "status", "--porcelain", "--", ALLOWED, cwd=wt):
            return "unchanged (mirror step %ds)" % took
        sh("git", "add", "--", ALLOWED, cwd=wt)
        sh("git", "commit", "-q", "-m",
           "demo: daily mirror refresh\n\nDone: scrubbed mirror rebuilt.\nNext: auto-merge on green CI.", cwd=wt)
        paths = sh("git", "diff", "--name-only", "origin/main...HEAD", cwd=wt).splitlines()
        fence(paths)
        stat = sh("git", "diff", "--shortstat", "origin/main...HEAD", cwd=wt)
        if dry:
            return "dry-run ok: would publish %d file(s), %s (mirror step %ds)" % (len(paths), stat, took)
        sh("git", "push", "-q", "origin", "HEAD:refs/heads/" + BRANCH, cwd=wt)
        url = sh("gh", "pr", "create", "--base", "main", "--head", BRANCH, "--title",
                 "demo: daily mirror refresh", "--body", "Data-only. Auto-merges on green CI (D295).", cwd=wt)
        num = url.rsplit("/", 1)[-1]
        fence(sh("gh", "pr", "diff", num, "--name-only", cwd=wt).splitlines())
        sh(str(MERGE), num, "--confirm", cwd=wt)
        return "merged PR %s (mirror step %ds)" % (num, took)
    finally:
        sh("git", "worktree", "remove", "--force", str(wt), cwd=root, check=False)
        sh("git", "branch", "-q", "-D", BRANCH, cwd=root, check=False)


def agent(remove):
    plist = Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")
    uid = "gui/%d" % os.getuid()
    if remove:
        subprocess.run(["launchctl", "bootout", "%s/%s" % (uid, LABEL)], capture_output=True)
        plist.unlink(missing_ok=True)
        print("removed", LABEL)
        return 0
    if (HERE.parent.parent / ".git").is_file():
        print("refusing: linked worktree. Install from the main checkout.")
        return 1
    payload = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(HERE)],
        "WorkingDirectory": str(HERE.parent.parent),
        "StartCalendarInterval": {"Hour": 4, "Minute": 30},
        "StandardOutPath": str(LOG.with_suffix(".out")),
        "StandardErrorPath": str(LOG.with_suffix(".out")),
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    }
    plist.parent.mkdir(parents=True, exist_ok=True)
    with open(plist, "wb") as f:
        plistlib.dump(payload, f)
    subprocess.run(["launchctl", "bootout", "%s/%s" % (uid, LABEL)], capture_output=True)
    r = subprocess.run(["launchctl", "bootstrap", uid, str(plist)], capture_output=True, text=True)
    print("bootstrap failed: " + r.stderr.strip() if r.returncode else "installed %s, daily 04:30" % LABEL)
    return r.returncode


def selftest():
    def refuses(paths):
        try:
            fence(paths)
        except Stop:
            return True
        return False
    assert not refuses([ALLOWED + "a.json", ALLOWED + "photos/b.jpg"]), "green: mirror-only diff"
    assert refuses([ALLOWED + "a.json", "scripts/x.py"]), "red: outside path"
    assert refuses(["demo-assets/mirror-evil/a"]), "red: sibling prefix"
    assert refuses([ALLOWED + "../photos/a"]), "red: traversal"
    # a real git diff, not just the function
    d = tempfile.mkdtemp()
    try:
        def g(*a):
            return sh("git", "-c", "user.name=t", "-c", "user.email=t@t", *a, cwd=d)
        g("init", "-q", "-b", "main")
        Path(d, "demo-assets/mirror").mkdir(parents=True)
        Path(d, "demo-assets/mirror/a").write_text("1")
        Path(d, "other").write_text("1")
        g("add", ".")
        g("commit", "-q", "-m", "base")
        g("checkout", "-q", "-b", "x")
        Path(d, "demo-assets/mirror/a").write_text("2")
        g("commit", "-qam", "ok")
        fence(g("diff", "--name-only", "main...HEAD").splitlines())
        Path(d, "other").write_text("2")
        g("commit", "-qam", "bad")
        assert refuses(g("diff", "--name-only", "main...HEAD").splitlines()), "red: real diff"
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("demo-mirror-daily-selftest: ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--agent", action="store_true")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        sys.exit(0)
    if a.agent:
        sys.exit(agent(a.remove))
    try:
        log(run(a.dry_run))
    except Stop as e:
        log("stopped, nothing published: %s" % e)
        sys.exit(1)
    except Exception as e:  # anything else: publish nothing, say why
        log("error, nothing published: %r" % e)
        sys.exit(1)
