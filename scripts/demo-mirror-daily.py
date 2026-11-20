#!/usr/bin/env python3
"""Weekly demo refresh (D295, docs/specs/demo.md §13). Owner's Mac, main tree only.

Cuts a throwaway worktree from fresh origin/main, runs `make demo-mirror` there, and
publishes the result ONLY if `demo-assets/mirror/` changed and the diff touches nothing
else. Any error: publish nothing, log why. One log line per run.

  demo-mirror-daily.py [--dry-run]   stop before push, print what would go out
  demo-mirror-daily.py --agent [--remove]   install / remove the weekly launchd job
  demo-mirror-daily.py --selftest    the fence and the wait for the PR's check go red, then green

The fence is what makes the standing auto-merge grant safe: `fence()` refuses any path
outside `demo-assets/mirror/`, checked on the local diff and again on the PR's own diff.
"""
import argparse
import contextlib
import datetime
import fcntl
import json
import os
import plistlib
import posixpath
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ALLOWED = "demo-assets/mirror/"
BRANCH = "demo/mirror-refresh"
LABEL = "com.banchi.demo-mirror-daily"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import ports  # noqa: E402

LOG = ports.machine_dir() / "demo-mirror-daily.log"
MERGE = Path.home() / ".claude" / "bin" / "merge"
SOURCE = Path.home() / "Developer" / "banchi"
HERE = Path(__file__).resolve()
LSOF_TIMEOUT = 20  # seconds; read when drop_tree runs
TERM_GRACE_SECONDS = 2  # a worker that traps SIGTERM gets this long before SIGKILL
REMOVE_RETRY_SECONDS = 6  # a late writer may recreate the folder; retry removal this long


CHECK = "all-jobs-passed"  # the one check branch protection requires; the merge tool refuses while it is pending
PENDING = ("queued", "in_progress", "pending", "waiting", "requested")  # check-run statuses before completed
CHECK_POLL_SECONDS = 60 # one read a minute, no faster
CHECK_WAIT_SECONDS = 20 * 60  # the cap; a run that is slower than this leaves the PR for clear_stale_pr


class Stop(Exception):
    pass


class Unreadable(Stop):
    """The check's status came back in a shape this script does not know: stop now, do not poll on."""


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


def read_check(head, cwd):
    """(status, conclusion) of the newest `all-jobs-passed` check run on `head`, REST API;
    (None, None) while the run has not created it yet. The merge tool has no wait flag."""
    out = sh("gh", "api", "repos/{owner}/{repo}/commits/%s/check-runs?per_page=100" % head, "--jq",
             '[.check_runs[] | select(.name == "%s")] | sort_by(.id) | last // empty'
             ' | [.status, .conclusion] | @tsv' % CHECK, cwd=cwd)
    if not out:
        return None, None
    parts = out.split("\t")
    # sh() strips the trailing tab, so a run with no conclusion yet arrives as one field: the status alone.
    if len(parts) == 1 and parts[0] in PENDING:
        return parts[0], ""
    if len(parts) != 2 or parts[0] not in PENDING + ("completed",):
        raise Unreadable("checks: cannot read %s status from %r" % (CHECK, out[:80]))
    return parts[0], parts[1]


def wait_for_check(read, sleep=time.sleep, clock=time.monotonic):
    """Block until `read()` says the check completed. Returns only on success; a failure, or still
    pending at the cap, is a Stop and the PR stays open for the next run's clear_stale_pr.
    A failed read (network) is retried until the cap."""
    deadline = clock() + CHECK_WAIT_SECONDS
    state = "not started"
    while True:
        try:
            status, conclusion = read()
            state = status or "not started"
        except Unreadable:
            raise
        except Stop as e:  # gh could not reach GitHub: try again next minute
            status, conclusion, state = None, None, "unreadable (%s)" % e
        if status == "completed":
            if conclusion == "success":
                return
            raise Stop("checks: %s concluded %s on the PR head; PR left open" % (CHECK, conclusion or "unknown"))
        if clock() >= deadline:
            raise Stop("checks: %s still %s after %ds; PR left open" % (CHECK, state, CHECK_WAIT_SECONDS))
        sleep(CHECK_POLL_SECONDS)


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


def cwd_pids(wt):
    """Pids (other than ours) whose working directory is wt or under it."""
    try:
        out = subprocess.run(["lsof", "-d", "cwd", "-Fpn"], capture_output=True, text=True, timeout=LSOF_TIMEOUT).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    pids, pid, real = [], None, os.path.realpath(wt)  # lsof prints real paths (/private/var, not /var)
    for line in out.splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("n") and pid != os.getpid() and (line[1:] == real or line[1:].startswith(real + os.sep)):
            pids.append(pid)
    return pids


def ancestors():
    """This process's pid and its parents' up the chain, read with `ps`; a failed read ends the chain."""
    chain, pid = {os.getpid()}, os.getppid()
    while pid > 1 and pid not in chain:
        chain.add(pid)
        try:
            pid = int(subprocess.run(["/bin/ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True,
                                     timeout=LSOF_TIMEOUT).stdout)
        except (OSError, ValueError, subprocess.SubprocessError):
            break
    return chain


def drop_tree(root, wt):
    """Remove a throwaway tree. Returns "" when it is gone, else why not; never raises, so a
    removal failure cannot replace what a run did. The demo server's sweep watcher starts inside
    the tree and rewrites its record after a removal, so stop the tree's servers first, give a
    worker that outlives SIGTERM two seconds, then SIGKILL what still stands in the tree, and
    retry the removal for a few seconds."""
    if wt.is_symlink():
        return "%s is a symlink; left alone" % wt
    note = ""
    j = subprocess.run([sys.executable, str(HERE.parent / "janitor.py"), "--teardown", str(wt)],
                       cwd=root, capture_output=True, text=True)
    if j.returncode:
        note = " (janitor teardown exited %d)" % j.returncode
    if j.returncode != 3:  # 3: a session still stands in the tree, so kill nothing
        end = time.time() + TERM_GRACE_SECONDS
        while cwd_pids(wt) and time.time() < end:
            time.sleep(0.1)
        keep = ancestors()
        for pid in cwd_pids(wt):
            if pid not in keep:
                with contextlib.suppress(OSError):
                    os.kill(pid, signal.SIGKILL)
    end = time.time() + REMOVE_RETRY_SECONDS
    while True:
        sh("git", "worktree", "remove", "--force", str(wt), cwd=root, check=False)
        shutil.rmtree(wt, ignore_errors=True)
        sh("git", "worktree", "prune", cwd=root, check=False)
        if not os.path.lexists(wt) or time.time() > end:
            break
        time.sleep(0.2)
    return "could not remove %s; delete it by hand%s" % (wt, note) if os.path.lexists(wt) else ""


def run(dry):
    """_run's verdict, or its Stop, with any failure to remove the throwaway tree appended."""
    left = []
    try:
        verdict = _run(dry, left)
    except Stop as e:
        if left:
            raise Stop("%s; %s" % (e, left[0])) from e
        raise
    except BaseException:  # also Ctrl-C: the leftover note is still worth a line
        if left:
            log(left[0])
        raise
    return "%s; %s" % (verdict, left[0]) if left else verdict


def _run(dry, left):
    root = main_tree()
    wts = root / ".claude" / "worktrees"
    wt = wts / ("demo-mirror-daily-%d" % time.time())
    sh("git", "worktree", "prune", cwd=root, check=False)  # a tree deleted by hand still holds the branch
    # The job holds an exclusive lock, so any sibling is a leftover of a run that never reached its finally.
    for d in wts.glob("demo-mirror-daily-*") if wts.is_dir() else []:
        if re.fullmatch(r"demo-mirror-daily-\d+", d.name) and d != wt and d.is_dir() and not d.is_symlink():
            bad = drop_tree(root, d)
            if bad:
                log("sweep: " + bad)
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
           "demo: mirror refresh\n\nDone: scrubbed mirror rebuilt.\nNext: auto-merge on green CI.", cwd=wt)
        paths = fence_raw(sh("git", "diff", "--raw", "--no-renames", "origin/main...HEAD", cwd=wt).splitlines())
        stat = sh("git", "diff", "--shortstat", "origin/main...HEAD", cwd=wt)
        if dry:
            return "dry-run ok: would publish %d file(s), %s (mirror step %ds)" % (len(paths), stat, took)
        sh("git", "push", "-q", "origin", "HEAD:refs/heads/" + BRANCH, cwd=wt)
        url = sh("gh", "pr", "create", "--base", "main", "--head", BRANCH, "--title",
                 "demo: mirror refresh", "--body", "Data-only. Auto-merges on green CI (D295).", cwd=wt)
        num = url.rsplit("/", 1)[-1]
        files = json.loads(sh("gh", "api", "--paginate", "--slurp", "repos/{owner}/{repo}/pulls/%s/files" % num, cwd=wt))
        fence_pr_files([f for page in files for f in page])
        head = sh("git", "rev-parse", "HEAD", cwd=wt)
        check_head(sh("gh", "pr", "view", num, "--json", "headRefOid", "--jq", ".headRefOid", cwd=wt), head)
        wait_for_check(lambda: read_check(head, wt))
        m =subprocess.run([str(MERGE), num, "--confirm"], cwd=wt, capture_output=True, text=True)
        if m.returncode:
            reason = (m.stderr or m.stdout).strip()[-300:]
            if sh("gh", "pr", "view", num, "--json", "state", "--jq", ".state", cwd=wt) == "MERGED":
                return "merged PR %s; local sync failed: %s" % (num, reason)
            raise Stop("merge of PR %s failed: %s" % (num, reason))
        return "merged PR %s (mirror step %ds)" % (num, took)
    finally:
        bad = drop_tree(root, wt)
        if bad:
            left.append(bad)
        sh("git", "branch", "-q", "-D", BRANCH, cwd=root, check=False)


def agent(remove):
    plist = Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")
    uid = "gui/%d" % os.getuid()
    if remove:
        subprocess.run(["launchctl", "bootout", "%s/%s" % (uid, LABEL)], capture_output=True)
        plist.unlink(missing_ok=True)
        ports.remove_old_agent(LABEL)
        print("removed", LABEL)
        return 0
    if (HERE.parent.parent / ".git").is_file():
        print("refusing: linked worktree. Install from the main checkout.")
        return 1
    payload = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(HERE)],
        "WorkingDirectory": str(HERE.parent.parent),
        "StartCalendarInterval": {"Weekday": 0, "Hour": 4, "Minute": 30},  # launchd: 0 is Sunday
        "StandardOutPath": str(LOG.with_suffix(".out")),
        "StandardErrorPath": str(LOG.with_suffix(".out")),
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    }
    plist.parent.mkdir(parents=True, exist_ok=True)
    with open(plist, "wb") as f:
        plistlib.dump(payload, f)
    subprocess.run(["launchctl", "bootout", "%s/%s" % (uid, LABEL)], capture_output=True)
    r = subprocess.run(["launchctl", "bootstrap", uid, str(plist)], capture_output=True, text=True)
    print("bootstrap failed: " + r.stderr.strip() if r.returncode else "installed %s, weekly Sunday 04:30" % LABEL)
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
    # the merge waits for the PR head's own check: pending, pending, then green returns, one read a minute
    def waits(reads):
        """Run wait_for_check over scripted reads on a fake clock. -> (result, sleeps), result 'ok' or the Stop text."""
        script, now, sleeps = list(reads), [0.0], []

        def read():
            r = script.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        def sleep(s):
            sleeps.append(s)
            now[0] += s
        try:
            wait_for_check(read, sleep=sleep, clock=lambda: now[0])
            return "ok", sleeps
        except Stop as e:
            return str(e), sleeps
    res, sleeps = waits([(None, None), ("queued", ""), ("in_progress", ""), ("completed", "success")])
    assert res == "ok" and sleeps == [CHECK_POLL_SECONDS] * 3, "green: waits out pending, then merges: %r %r" % (res, sleeps)
    res, sleeps = waits([("in_progress", ""), ("completed", "failure")])
    assert "concluded failure" in res and len(sleeps) == 1, "red: a failed check never merges: %r" % res
    for c in ("cancelled", "skipped", "timed_out", ""):
        assert "concluded" in waits([("completed", c)])[0], "red: only success merges (%r)" % c
    res, sleeps = waits([("in_progress", "")] * 1000)
    assert "still in_progress" in res and CHECK_POLL_SECONDS * len(sleeps) <= CHECK_WAIT_SECONDS \
        and len(sleeps) == CHECK_WAIT_SECONDS // CHECK_POLL_SECONDS, "red: a check that never ends stops at the cap: %r" % res
    res, sleeps = waits([Stop("gh api failed"), (None, None), ("completed", "success")])
    assert res == "ok", "green: a failed read is retried, not fatal"
    assert "unreadable" in waits([Stop("gh api failed")] * 1000)[0], "red: reads that never work stop at the cap"
    assert "cannot read" in waits([Unreadable("checks: cannot read")])[0] and not waits([Unreadable("x")])[1], \
        "red: an unknown shape stops at once"
    assert CHECK_POLL_SECONDS >= 60, "one read a minute at most"
    # read_check: the tsv row of the newest check run, none yet, or a shape it does not know
    g = globals()
    real_sh = g["sh"]
    try:
        for out, want in (("in_progress", ("in_progress", "")), ("queued", ("queued", "")),  # sh() strips the tab
                          ("in_progress\t", ("in_progress", "")),("completed\tsuccess", ("completed", "success")), ("", (None, None))):
            g["sh"] = lambda *a, cwd=None, check=True, out=out: out
            assert read_check("abc", None) == want, "green: read_check %r" % out
        for bad in ("[[]]", "completed", "bogus", "bogus\tsuccess", "in_progress\tx\ty"):
            g["sh"] = lambda *a, cwd=None, check=True, bad=bad: bad
            try:
                read_check("abc", None)
                raise AssertionError("red: read_check took an unknown shape %r" % bad)
            except Unreadable:
                pass
    finally:
        g["sh"] = real_sh
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
