#!/usr/bin/env python3
# Protects: The daily demo mirror never publishes a bundle that names a card whose photograph it did not commit.
"""The daily mirror ships every photograph its bundle names (D295, D172).
Incident: `.gitignore`'s bare `photos` also matched demo-assets/mirror/photos/, `git add` skipped
the new photographs without a word, and the bundle merged naming cards with no photograph.
Three cases, each red on the old code. Run: python3 scripts/demo-mirror-daily-photos-selftest.py"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIRROR = "demo-assets/mirror/"
failures = []


def git(cwd, *a, check=True):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd,
                          capture_output=True, text=True, check=check)


def ignored(path):
    d = tempfile.mkdtemp()
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
    base = Path(tempfile.mkdtemp())
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
sys.exit(1 if failures else 0)
