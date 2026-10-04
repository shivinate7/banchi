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
import fcntl
import json
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


def fence_raw(lines):
    """`git diff --raw --no-renames` lines: paths inside, and only regular files (no symlink,
    submodule or mode change). A rename shows as a delete plus an add, so a source outside counts."""
    paths = []
    for line in lines:
        meta, path = line.split("\t", 1)
        old_mode, new_mode = meta.split()[0].lstrip(":"), meta.split()[1]
        if old_mode not in ("000000", "100644") or new_mode not in ("000000", "100644"):
            raise Stop("fence: non-regular file or mode change: %s" % path)
        paths.append(path)
    fence(paths)
    return paths


def fence_pr_files(files):
    """The PR files API rows: filename AND previous_filename must both be inside."""
    fence([p for f in files for p in (f["filename"], f.get("previous_filename")) if p])


def check_head(pr_oid, local_oid):
    if pr_oid != local_oid:
        raise Stop("fence: PR head %s is not the fenced local HEAD %s" % (pr_oid[:8], local_oid[:8]))


def clear_stale_pr(root):
    """An open PR on our branch blocks every later push. Red or over a day old: close it and
    delete the branch. Otherwise stop and name it."""
    rows = json.loads(sh("gh", "pr", "list", "--head", BRANCH, "--state", "open", "--json",
                         "number,createdAt,statusCheckRollup", cwd=root) or "[]")
    for pr in rows:
        age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(
            pr["createdAt"].replace("Z", "+00:00"))
        red = any(c.get("conclusion") == "FAILURE" for c in pr["statusCheckRollup"] or [])
        if not red and age < datetime.timedelta(days=1):
            raise Stop("open PR #%d on %s still in flight" % (pr["number"], BRANCH))
        sh("gh", "pr", "close", str(pr["number"]), "--delete-branch", cwd=root)
    # a leftover remote branch with no open PR would also reject our push
    sh("git", "push", "origin", "--delete", BRANCH, cwd=root, check=False)


def check_photos(wt):
    """Refuse a bundle that names a card whose photograph is neither staged nor tracked.
    Incident: PR #695 merged a bundle naming 62 cards with no photographs (an ignore rule hid them)."""
    have = set(sh("git", "ls-files", "--", ALLOWED + "photos", cwd=wt).splitlines())
    miss = []
    for f in sorted((Path(wt) / ALLOWED / "bundle").glob("*.json")):
        cards = json.loads(f.read_text())["responses"].get("/inventory", {}).get("body", {}).get("cards", {})
        miss += ["%sphotos/%s/%s.jpg" % (ALLOWED, c["box"], c["index"]) for c in cards.values() if c.get("photo")]
    miss = [m for m in miss if m not in have]
    if miss:
        raise Stop("photos: bundle names %d card(s) with no staged or tracked photograph, first: %s" % (len(miss), miss[0]))


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
    clear_stale_pr(root)
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
        check_photos(wt)
        sh("git", "commit", "-q", "-m",
           "demo: daily mirror refresh\n\nDone: scrubbed mirror rebuilt.\nNext: auto-merge on green CI.", cwd=wt)
        paths = fence_raw(sh("git", "diff", "--raw", "--no-renames", "origin/main...HEAD", cwd=wt).splitlines())
        stat = sh("git", "diff", "--shortstat", "origin/main...HEAD", cwd=wt)
        if dry:
            return "dry-run ok: would publish %d file(s), %s (mirror step %ds)" % (len(paths), stat, took)
        sh("git", "push", "-q", "origin", "HEAD:refs/heads/" + BRANCH, cwd=wt)
        url = sh("gh", "pr", "create", "--base", "main", "--head", BRANCH, "--title",
                 "demo: daily mirror refresh", "--body", "Data-only. Auto-merges on green CI (D295).", cwd=wt)
        num = url.rsplit("/", 1)[-1]
        files = json.loads(sh("gh", "api", "--paginate", "--slurp", "repos/{owner}/{repo}/pulls/%s/files" % num, cwd=wt))
        fence_pr_files([f for page in files for f in page])
        check_head(sh("gh", "pr", "view", num, "--json", "headRefOid", "--jq", ".headRefOid", cwd=wt),
                   sh("git", "rev-parse", "HEAD", cwd=wt))
        m = subprocess.run([str(MERGE), num, "--confirm"], cwd=wt, capture_output=True, text=True)
        if m.returncode:
            reason = (m.stderr or m.stdout).strip()[-300:]
            if sh("gh", "pr", "view", num, "--json", "state", "--jq", ".state", cwd=wt) == "MERGED":
                return "merged PR %s; local sync failed: %s" % (num, reason)
            raise Stop("merge of PR %s failed: %s" % (num, reason))
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
    # rename-in: the source outside the mirror shows up with --no-renames, and in the PR API
    assert refuses(["other", ALLOWED + "a"]), "red: rename-in, local"
    try:
        fence_pr_files([{"filename": ALLOWED + "a", "previous_filename": "other"}])
        raise AssertionError("red: rename-in, PR side")
    except Stop:
        pass
    fence_pr_files([{"filename": ALLOWED + "a"}])
    # symlink, submodule, mode change
    ok = ":000000 100644 0000000 1111111 A\t" + ALLOWED + "a"
    fence_raw([ok])
    for bad in (":000000 120000 0000000 1111111 A\t", ":000000 160000 0000000 1111111 A\t",
                ":100644 100755 1111111 1111111 M\t"):
        try:
            fence_raw([bad + ALLOWED + "a"])
            raise AssertionError("red: " + bad)
        except Stop:
            pass
    # moved head
    check_head("abc", "abc")
    try:
        check_head("abc", "def")
        raise AssertionError("red: moved head")
    except Stop:
        pass
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
    LOG.parent.mkdir(parents=True, exist_ok=True)
    lock = open(LOG.with_suffix(".lock"), "w")  # noqa: SIM115 held for the process life
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("skipped: another run holds the lock")
        sys.exit(0)
    try:
        log(run(a.dry_run))
    except Stop as e:
        log("stopped, nothing published: %s" % e)
        sys.exit(1)
    except Exception as e:  # anything else: publish nothing, say why
        log("error, nothing published: %r" % e)
        sys.exit(1)
