#!/usr/bin/env python3
"""The supervisor's build job, proved against a throwaway tree (D138).

Protects: The supervisor rebuilds a stale bundle, keeps the old one when a build fails, and keeps Python and screen edits on separate tracks.
Governs: D18, D138, D261

WHAT IS UNDER TEST IS THE SUPERVISOR, NOT VITE. The behaviours that matter here are all the
supervisor's own: when it decides the bundle is behind, what it does while a build is running,
what it leaves on disk when one fails, and whether a Python edit and a screen edit stay on
separate tracks. None of that is a fact about the TypeScript compiler, so the "build" in this
tree is a shell script that writes one file — which is also what keeps this ~10s and free of
node, and lets a FAILING build be produced on demand rather than by breaking a real screen.

THE TREE IS A COPY, NOT THIS ONE, and the reason is the same one `scripts/janitor-selftest.sh`
gives: this script starts and stops supervisors, writes pidfiles and swaps directories, and the
checkout it runs in may have the owner's live server in it. A copy has its own `.serve/`, its
own ports and nothing anybody is using.

THE PORT IS PINNED WITH `BANCHI_PORT`, TO A FREE SOCKET THE OS HANDS OUT. The first time this
script ran, the derivation asked whether the directory was a LINKED WORKTREE. A
`shutil.copytree` of this repo is not one, so the copy called itself the main checkout and
claimed :8000, the owner's live capture server over their real store. Measured: `up` in the copy
refused with ":8000 is already held". Since D261 (a copied tree never gets the
live port), only a `.git` DIRECTORY keeps :8000, so a copy with no `.git` takes a slot from its
path. The pin stays: a slot can collide with another worktree's, and a free socket cannot.

IN `make check`, NEVER IN THE GIT HOOK. D18: it writes, and nothing that writes may gate a
commit. Same placement and same reason as `audit-self-test`, `githooks-selftest`,
`janitor-selftest` and `verdict-selftest`.
"""

import argparse
import contextlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
# `port_split()` is a pure function over a real socket and `lsof` — tested directly, by
# import, rather than through a copied tree and a running supervisor like everything else in
# this file. It has no supervisor state to isolate. Aliased: this file already defines its
# own module-level `serve()` (the CLI-invoking helper below), which would shadow the import.
import serve as serve_module  # noqa: E402

# What a copy needs to run a supervisor and a capture server. `app/` is NOT copied — the tree
# gets a stub one, because a real `app/` means `node_modules` and a real `vite build`, which is
# the one thing this script is deliberately not testing.
CARRY = (
    "scripts/serve.py",
    # THE SUPERVISOR IS MADE OF THIS FILE TOO SINCE THE SELF-SYNC — it is in `SELF_FILES` and
    # imported at module scope, so a tree without it cannot start one at all.
    "scripts/primary_sync.py",
    # `do_up` IMPORTS THIS AT MODULE SCOPE SINCE 7e80e3df (lane R) — it marks the real
    # detached supervisor child directly rather than through the Makefile wrapper. A tree
    # without it fails every `serve.py` invocation at import time, before `.serve/` is ever
    # created, which is what turned into a FileNotFoundError on `supervisor.log` far downstream
    # rather than the ModuleNotFoundError this actually was.
    "scripts/reap_mark.py",
    # `reap_mark.py` itself imports `checkout_root` and `proc_start_epoch` from here.
    "scripts/reap.py",
    "envfile.py",
    "server",
    "store",
    "pipeline",
    "cli",
    "identify",
    "geometry",
    "codes",
    "fixtures",
)

# The stub build. Writes the four files a real build would, so `do_app_file` has something to
# serve and `app_built` is true — and reads `SELFTEST_BUILD` to decide whether to succeed, fail
# or take its time, which is what lets one script exercise all three.
BUILD_STUB = """#!/bin/sh
# A stand-in for `vite build`. Vite's own arguments arrive verbatim and `--outDir` IS HONOURED
# — which is not a detail. A stub that hardcoded its output directory would write to
# `dist.next` no matter what the supervisor asked for, so a supervisor mutated to build
# straight into `dist/` would still pass every arm of this script. Measured: it did.
out=dist.next
while [ $# -gt 0 ]; do
  [ "$1" = "--outDir" ] && { out="$2"; shift; }
  shift
done
mode="${SELFTEST_BUILD:-pass}"
sleep_for="${SELFTEST_BUILD_SLEEP:-0}"
[ "$sleep_for" = "0" ] || sleep "$sleep_for"
if [ "$mode" = "fail" ]; then
  echo "error TS1005: ';' expected."
  exit 2
fi
rm -rf "$out"
mkdir -p "$out/assets"
printf '<!doctype html><title>Banchi</title><!--%s-->' "$(cat generation 2>/dev/null || echo 0)" > "$out/index.html"
printf 'export const build = %s\\n' "$(cat generation 2>/dev/null || echo 0)" > "$out/assets/main-aaaa.js"
printf '{"id":"/"}' > "$out/manifest.webmanifest"
exit 0
"""

PASS = "\033[32mok\033[0m" if sys.stdout.isatty() else "ok"
FAIL = "\033[31mFAIL\033[0m" if sys.stdout.isatty() else "FAIL"

failures: list[str] = []

# Each throwaway tree's pinned capture port. Keyed by tree so `serve()` needs no extra
# argument at nineteen call sites.
PORTS: Dict[Path, int] = {}


def check(condition: bool, message: str) -> None:
    print(f"  {PASS if condition else FAIL}  {message}")
    if not condition:
        failures.append(message)


def build_tree(where: Path) -> Path:
    """A checkout that can run a supervisor, with a stub `app/` in place of the real one."""
    tree = where / "tree"
    tree.mkdir()
    for name in CARRY:
        source = ROOT / name
        if not source.exists():
            continue
        target = tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(
                source, target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules"),
            )
        else:
            shutil.copy2(source, target)

    app = tree / "app"
    (app / "src").mkdir(parents=True)
    (app / "public").mkdir()
    # `node_modules` has to LOOK present or `build_app` refuses before it ever runs the stub —
    # which is correct behaviour and is asserted in its own arm below, not here.
    (app / "node_modules").mkdir()
    (app / "src" / "App.tsx").write_text("export default function App() {}\n", "utf-8")
    (app / "index.html").write_text("<!doctype html>\n", "utf-8")
    (app / "package.json").write_text('{"name": "stub"}\n', "utf-8")
    (app / "package-lock.json").write_text('{"lockfileVersion": 3}\n', "utf-8")
    (app / "generation").write_text("1\n", "utf-8")

    # `npx` is resolved off PATH by `build_app`, so the stub goes in a directory this script
    # puts FIRST on the child's PATH. That is the whole substitution: the supervisor runs
    # exactly the command it always runs.
    # Beside the tree, because `serve()` finds it at `tree.parent / "bin"` — so a second tree
    # in its own directory gets its own stub rather than reaching for the first one's.
    bin_dir = where / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "npx"
    stub.write_text(BUILD_STUB, "utf-8")
    stub.chmod(0o755)
    (bin_dir / "npm").write_text("#!/bin/sh\nexit 0\n", "utf-8")
    (bin_dir / "npm").chmod(0o755)
    PORTS[tree] = free_port()
    return tree


def make_primary_checkout(tree: Path) -> None:
    """Turn the throwaway tree into a PRIMARY checkout with a real `main`.

    D158 is the entry.

    REPRODUCED RATHER THAN ASSERTED ABOUT. The situation this guard exists for is one
    directory — the one D138 serves the owner's real store out of — standing on a feature
    branch, and the only way to know the supervisor refuses it is to put a real supervisor in
    a real checkout in that real state. A mocked `off_main` would prove the arms call it.

    ONLY THREE FILES ARE TRACKED, and that is the whole trick: the switch has to CHANGE a
    watched file or no reload is scheduled and the guard is never reached.
    `server/capture_server.py` stands for the ordinary reload, `app/src/App.tsx` for the
    build, and `scripts/serve.py` for the re-exec, which is the arm that matters most.
    Tracking the rest would add `fixtures/` to a git index for nothing.

    `BANCHI_MAIN=off` throughout: this repo's own pre-commit and ref hooks may be armed
    through the ambient config, and the fixture's seed commits are not the thing under test.
    """
    env = dict(os.environ, BANCHI_MAIN="off")

    def run(*argv: str) -> None:
        subprocess.run(["git", *argv], cwd=str(tree), env=env,  # noqa: S603, S607
                       capture_output=True, text=True, check=False)

    run("init", "-q", "-b", "main")
    run("config", "user.email", "selftest@example.com")
    run("config", "user.name", "selftest")
    run("config", "commit.gpgsign", "false")
    run("add", "--", "scripts/serve.py", "server/capture_server.py", "app/src/App.tsx")
    run("commit", "-qm", "main")

    # A branch that moves an ordinary watched file: the child-restart path.
    run("switch", "-q", "-c", "feature")
    watched = tree / "server" / "capture_server.py"
    watched.write_text(watched.read_text("utf-8") + "\n# branch\n", "utf-8")
    run("commit", "-qam", "a watched file moves on a branch")

    # AND A BRANCH THAT DELETES THE GUARD FROM `scripts/serve.py` ITSELF. That file is in
    # SELF_FILES, so adopting it is a `_reexec` — the supervisor replacing its own image with
    # the code on disk. If the branch check ran after that, this branch's unguarded copy would
    # be the one answering it, which is no guard at all. This is the arm that pins the order.
    # A branch that moves ONLY `app/src`: the build path. The two watch sets are independent
    # by design (D138), so this branch reaches `_check_app` and never `_restart_for` — which
    # is why the app half needs a stand-down of its own and an arm of its own.
    run("switch", "-q", "-c", "app-only", "main")
    tsx = tree / "app" / "src" / "App.tsx"
    tsx.write_text(tsx.read_text("utf-8") + "\n// branch\n", "utf-8")
    run("commit", "-qam", "only the app moves on a branch")

    run("switch", "-q", "-c", "no-guard", "main")
    serve_py = tree / "scripts" / "serve.py"
    text = serve_py.read_text("utf-8")
    gutted = text.replace(
        'if os.environ.get(SERVE_MAIN_ENV) == "off":\n        return None',
        "return None  # guard deleted by this branch",
        1,
    )
    assert gutted != text, "the fixture could not find the guard to delete"
    serve_py.write_text(gutted, "utf-8")
    run("commit", "-qam", "a branch that predates the guard")
    run("switch", "-q", "main")


def give_origin(tree: Path) -> None:
    """Give the fixture a real `origin` whose `main` is one commit AHEAD of the tree's.

    THE EXISTING ARMS DELIBERATELY HAVE NO ORIGIN, and that is what keeps them meaning what
    they meant. `scripts/primary_sync.py` answers `not-subject` for a clone with no
    `refs/remotes/origin/main` — there is no authority to sync to — so every refusal arm above
    still exercises the refusal rather than the sync that now precedes it. This one builds the
    other half: a tree that CAN be synced, so the supervisor's new behaviour is visible.

    The extra commit lands on `app/src/App.tsx`, which is tracked in this fixture, so the
    fast-forward actually changes a watched file. A sync that moved only untracked history
    would prove the ref moved and nothing about the tree the rig serves.
    """
    env = dict(os.environ, BANCHI_MAIN="off")

    def run(where: Path, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *argv], cwd=str(where), env=env,  # noqa: S603, S607
                              capture_output=True, text=True, check=False)

    origin = tree.parent / "origin.git"
    run(tree.parent, "clone", "-q", "--bare", str(tree), str(origin))
    run(tree, "remote", "add", "origin", str(origin))

    # The commit that puts origin ahead, authored in a scratch clone so the fixture tree itself
    # is never moved by the setup.
    scratch = tree.parent / "scratch"
    run(tree.parent, "clone", "-q", str(origin), str(scratch))
    for argv in (("config", "user.email", "selftest@example.com"),
                 ("config", "user.name", "selftest"),
                 ("config", "commit.gpgsign", "false")):
        run(scratch, *argv)
    tsx = scratch / "app" / "src" / "App.tsx"
    tsx.write_text(tsx.read_text("utf-8") + "\n// landed on origin/main\n", "utf-8")
    run(scratch, "commit", "-qam", "a commit only origin has")
    pushed = run(scratch, "push", "-q", "origin", "main")
    assert pushed.returncode == 0, f"the fixture could not push to its own origin: {pushed.stderr}"
    run(tree, "fetch", "-q", "origin")

    gap = run(tree, "rev-list", "--count",
              "refs/heads/main..refs/remotes/origin/main").stdout.strip()
    assert gap == "1", f"the fixture did not put origin ahead: {gap!r}"


def git_switch(tree: Path, branch: str) -> None:
    subprocess.run(["git", "switch", "-q", branch], cwd=str(tree),  # noqa: S603, S607
                   env=dict(os.environ, BANCHI_MAIN="off"),
                   capture_output=True, text=True, check=False)


def free_port() -> int:
    """A port the OS says is free right now. Bound, read, released — the standard idiom, and
    the small race it carries is the right trade against a hard-coded number that would make
    two runs of this script collide."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def serve_env(tree: Path, env: Optional[dict] = None) -> dict:
    child_env = dict(os.environ)
    child_env["BANCHI_HOME"] = str(tree / "home")
    child_env["BANCHI_PORT"] = str(PORTS[tree])
    child_env["PATH"] = f"{tree.parent / 'bin'}{os.pathsep}{child_env.get('PATH', '')}"
    child_env.update(env or {})
    return child_env


def serve(tree: Path, *args: str, env: Optional[dict] = None, timeout: int = 120):
    child_env = serve_env(tree, env)
    return subprocess.run(  # noqa: S603
        [sys.executable, str(tree / "scripts" / "serve.py"), *args],
        cwd=str(tree), env=child_env, capture_output=True, text=True, timeout=timeout,
    )


def report(tree: Path) -> dict:
    done = serve(tree, "report", "--json")
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        return {}


def get(port: int, path: str, timeout: float = 5.0):
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{port}{path}", headers={"Connection": "close"}
            ),
            timeout=timeout,
        ) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as refused:
        return int(refused.code), refused.read()
    except OSError:
        return 0, b""


def wait_until(predicate, seconds: float = 30.0, step: float = 0.25) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def build_logged(tree: Path) -> bool:
    """Has the last build the supervisor started logged its finish?"""
    text = supervisor_log(tree)
    return text.rfind("app built in") > text.rfind("rebuilding")


def supervisor_log(tree: Path) -> str:
    try:
        return (tree / ".serve" / "supervisor.log").read_text("utf-8")
    except OSError:
        return ""


def check_port_split() -> None:
    """`serve.port_split()` — the 2026-09-23 incident (D43), read-only, D127.

    TWO DISTINCT PROCESSES ON ONE PORT, ONE PER FAMILY, is what the incident measured: an
    IPv4 `0.0.0.0` listener and a LATER IPv6 `::` listener (`IPV6_V6ONLY=1`, so it takes only
    the IPv6 half rather than Task 1's own dual-stack fix) both bind successfully. This test
    reproduces exactly that — a socket bound in this process, and a second bound by a child
    process this test spawns and tears down — and asserts `port_split` calls it `"split"` and
    names both pids. A single listener, bound the same way, must report `"ok"` with nothing
    to print: the everyday case is not a warning.
    """
    print("\n  port_split — the 2026-09-23 incident: `localhost` may reach the wrong process")
    v4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    v4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    v4.bind(("0.0.0.0", 0))
    v4.listen(1)
    port = v4.getsockname()[1]
    v6 = subprocess.Popen([  # noqa: S603
        sys.executable, "-c",
        "import socket, time\n"
        "s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)\n"
        "s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)\n"
        f"s.bind(('::', {port}))\n"
        "s.listen(1)\n"
        "time.sleep(30)\n",
    ])
    try:
        status, lines = "unknown", []
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status, lines = serve_module.port_split(port)
            if status == "split":
                break
            time.sleep(0.1)
        check(status == "split", "two distinct processes on one port are reported SPLIT")
        text = "\n".join(lines)
        check(str(os.getpid()) in text, "naming this process's own pid (the IPv4 half)")
        check(str(v6.pid) in text, "and the spawned process's pid (the IPv6 half)")
        check("IPv4" in text and "IPv6" in text, "and which family each one holds")
    finally:
        v6.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            v6.wait(timeout=5)
        v4.close()

    lone = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lone.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    lone.bind(("127.0.0.1", 0))
    lone.listen(1)
    try:
        status, lines = serve_module.port_split(lone.getsockname()[1])
        check(status == "ok" and not lines, "one listener alone is `ok` — nothing to warn about")
    finally:
        lone.close()


# ---------------------------------------------------------------- idle restart (D176)
# The auto-restart and the app build wait until the owner has been idle for five minutes. A held
# restart fires at two hours, or at once when the skip file exists. The restart cases run in
# process against a clock the test owns, so no case waits for a window.
#
# THE CONTRACT THE BUILD KEEPS: `serve.IDLE_SECONDS` (300) and `serve.HOLD_CAP_SECONDS` (7200);
# the activity file `.serve/activity`, whose mtime is the last change; the skip file
# `.serve/restart-now`; and the Supervisor's own `pending`, `quiet_since`, `app_pending`,
# `app_quiet_since`, `_check_files`, `_check_app`, `_restart_for` and `_reap`. The predicate must
# read the clock through serve.py's module-level `time` name, which the cases replace.

NOW = 1_800_000_000.0  # a fixed epoch: no case reads the wall clock


class FakeClock:
    """Stands in for the `time` name serve.py reads. Time moves only when a case moves it."""

    def __init__(self, start: float) -> None:
        self.now = start

    def time(self) -> float:
        return self.now

    def monotonic(self) -> float:
        return self.now

    def sleep(self, _seconds: float) -> None:
        return None

    def __getattr__(self, name: str):
        return getattr(time, name)


@contextlib.contextmanager
def swapped(owner, **names):
    """Replace names on a module or an object for one block, then put them back."""
    saved = {name: getattr(owner, name) for name in names}
    for name, value in names.items():
        setattr(owner, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(owner, name, value)


_ABSENT = object()


@contextlib.contextmanager
def swapped_or_absent(owner, **names):
    """As `swapped`, for a name that may not exist yet: it is removed again on the way out."""
    saved = {name: getattr(owner, name, _ABSENT) for name in names}
    for name, value in names.items():
        setattr(owner, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is _ABSENT:
                delattr(owner, name)
            else:
                setattr(owner, name, value)


def run(step) -> str:
    """Run one step of a case. A raise is a failed case, not a dead script."""
    try:
        step()
        return ""
    except Exception as err:  # noqa: BLE001 — the case reports what raised
        return f" (raised {type(err).__name__}: {err})"


def idle_supervisor(base: Path, clock: FakeClock):
    """A Supervisor over a throwaway root whose restart is a recorder, not a spawn."""
    root = base / "root"
    (root / ".serve").mkdir(parents=True)
    sup = serve_module.Supervisor(root=root, watch=False)
    sup.fingerprint = serve_module.fingerprint(root)
    sup.app_fingerprint = serve_module.app_fingerprint(root)
    sup.quiet_since = clock.now - 10
    restarts: list = []
    sup._restart_for = lambda changed: restarts.append(list(changed))
    return sup, restarts


def touch_activity(root: Path, at: float) -> None:
    path = root / ".serve" / "activity"
    path.write_text("", "utf-8")
    os.utime(path, (at, at))


def activity_mtime(tree: Path) -> Optional[int]:
    try:
        return (tree / ".serve" / "activity").stat().st_mtime_ns
    except OSError:
        return None


def post(port: int, path: str, body: dict, timeout: float = 5.0) -> int:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Connection": "close"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status)
    except urllib.error.HTTPError as refused:
        return int(refused.code)
    except OSError:
        return 0


def check_idle_restart() -> None:
    print("\n  the restart and the app build wait for an idle owner (D176)")
    check(
        getattr(serve_module, "IDLE_SECONDS", None) == 300,
        "serve.IDLE_SECONDS is 300: a change holds the restart for five idle minutes (R-I1)",
    )
    check(
        getattr(serve_module, "HOLD_CAP_SECONDS", None) == 7200,
        "serve.HOLD_CAP_SECONDS is 7200: a held restart goes ahead after two hours (R-I2)",
    )
    clock = FakeClock(NOW)
    with tempfile.TemporaryDirectory() as tmp, swapped(serve_module, time=clock):
        where = Path(tmp)

        sup, restarts = idle_supervisor(where / "recent", clock)
        touch_activity(sup.root, clock.now - 10)
        sup.pending = {"scripts/serve.py"}
        error = run(sup._check_files)
        check(
            restarts == [] and "scripts/serve.py" in sup.pending,
            "a change 10 s old holds the restart, and the change stays pending" + error,
        )

        sup, restarts = idle_supervisor(where / "old", clock)
        touch_activity(sup.root, clock.now - 301)
        sup.pending = {"scripts/serve.py"}
        error = run(sup._check_files)
        check(
            restarts == [["scripts/serve.py"]],
            "a change 301 s old, past the five-minute window, restarts" + error,
        )

        sup, restarts = idle_supervisor(where / "cap", clock)
        sup.pending = {"scripts/serve.py"}
        fired_at = None
        error = ""
        for held in range(0, 7261, 60):
            clock.now = NOW + held
            touch_activity(sup.root, clock.now)  # the owner stays active the whole time
            error = run(sup._check_files)
            if restarts or error:
                fired_at = held
                break
        check(
            fired_at is not None and 7080 < fired_at <= 7260,
            "a restart held by activity every minute fires at the two-hour cap, "
            f"not before (fired at {fired_at} s)" + error,
        )

        sup, restarts = idle_supervisor(where / "missing", clock)
        sup.pending = {"scripts/serve.py"}
        error = run(sup._check_files)
        check(
            restarts == [["scripts/serve.py"]],
            "no activity file at all: the restart goes ahead, so a first boot is never held"
            + error,
        )

        sup, restarts = idle_supervisor(where / "unreadable", clock)
        touch_activity(sup.root, clock.now - 10)
        sup.pending = {"scripts/serve.py"}
        state = sup.root / ".serve"
        state.chmod(0o000)  # the file is there, and its mtime cannot be read
        try:
            error = run(sup._check_files)
        finally:
            state.chmod(0o755)
        check(
            restarts == [["scripts/serve.py"]],
            "an activity file that cannot be read counts as idle, so the restart goes ahead"
            + error,
        )

        sup, restarts = idle_supervisor(where / "skip", clock)
        touch_activity(sup.root, clock.now - 10)
        skip = sup.root / ".serve" / "restart-now"
        skip.write_text("", "utf-8")
        sup.pending = {"scripts/serve.py"}
        error = run(sup._check_files)
        check(
            restarts == [["scripts/serve.py"]],
            "the skip file fires a restart that a change 10 s old holds" + error,
        )
        check(not skip.exists(), "and the skip file is removed once it has fired")

        cases = (("held", 10, False), ("idle", 301, False), ("skip", 10, True))
        for label, age, skip_file in cases:
            sup = serve_module.Supervisor(root=where / f"app-{label}" / "root", watch=False)
            (sup.root / ".serve").mkdir(parents=True)
            sup.app_fingerprint = serve_module.app_fingerprint(sup.root)
            touch_activity(sup.root, clock.now - age)
            if skip_file:
                (sup.root / ".serve" / "restart-now").write_text("", "utf-8")
            sup.app_pending = True
            sup.app_quiet_since = clock.now - 10
            builds: list = []
            with swapped(
                serve_module,
                off_main=lambda root: None,
                app_stale=lambda root: True,
                build_app=lambda root: builds.append(str(root)) or True,
            ):
                error = run(sup._check_app)
            if label == "held":
                check(
                    builds == [] and sup.app_pending,
                    "a recent change holds the app build with the restart, and stays pending"
                    + error,
                )
            elif label == "idle":
                check(builds != [], "an app change 301 s old, past the window, builds" + error)
            else:
                check(
                    builds != [],
                    "the skip file fires a held app build as well as the restart (R-I4)" + error,
                )

        sup, restarts = idle_supervisor(where / "offmain", clock)
        del sup._restart_for  # the real method: this case is about what it does
        touch_activity(sup.root, clock.now - 301)
        sup.pending = {"scripts/serve.py"}
        spawned: list = []
        stood_down: list = []
        sup._sync_attempt = lambda branch: branch
        sup._stand_down = lambda branch: stood_down.append(branch)
        with swapped(
            serve_module,
            off_main=lambda root: "feature/x",
            spawn_capture=lambda root: spawned.append(str(root)) or None,
        ):
            error = run(sup._check_files)
        check(
            stood_down == ["feature/x"] and spawned == [],
            "an idle restart on a branch stands down before it spawns: the off-main guard "
            "still runs first" + error,
        )

        sup, restarts = idle_supervisor(where / "crash", clock)

        class Exited:
            pid = 4242
            returncode = 1

            def poll(self):
                return 1

        touch_activity(sup.root, clock.now - 10)  # a recent change, which must not hold a crash
        sup.capture = Exited()
        respawned: list = []
        sup._await_capture = lambda: None
        with swapped(serve_module, spawn_capture=lambda root: respawned.append(str(root)) or None):
            error = run(sup._reap)
        check(
            len(respawned) == 1,
            "a crashed capture server is respawned at once, whatever the activity file says"
            + error,
        )


def check_child_marks_activity() -> None:
    """The capture child writes `.serve/activity` when a request changes state (D176).

    An open tab polls reads all day. If a read marked activity, the restart would wait the full
    two hours every time, so the reads are asserted NOT to mark it.
    """
    print("\n  the capture child marks activity on a state change, and not on a read (D176)")
    with tempfile.TemporaryDirectory() as tmp:
        tree = build_tree(Path(tmp))
        port = PORTS[tree]
        serve(tree, "up")
        try:
            up = wait_until(lambda: get(port, "/status")[0] == 200)
            check(up, "the capture server comes up")
            before = activity_mtime(tree)
            get(port, "/status")
            post(port, "/pipeline/waiting", {})
            check(
                activity_mtime(tree) == before,
                "GET /status and POST /pipeline/waiting, the tab's polls, leave the activity "
                "file alone",
            )
            written = post(port, "/boxes", {"name": "Idle probe"})
            check(
                200 <= written < 300,
                f"POST /boxes, a state change, is accepted (answered {written})",
            )
            check(
                activity_mtime(tree) not in (None, before),
                "and that POST marks activity, so the supervisor holds the next restart",
            )
        finally:
            serve(tree, "down", "--confirm")


def check_cap_releases_build() -> None:
    print("\n  the two-hour cap fires the restart and the app build on one release (D176)")
    clock = FakeClock(NOW)
    builds: list = []
    with tempfile.TemporaryDirectory() as tmp, swapped(
        serve_module,
        time=clock,
        off_main=lambda root: None,
        app_stale=lambda root: True,
        build_app=lambda root: builds.append(str(root)) or True,
    ):
        sup, restarts = idle_supervisor(Path(tmp) / "cap-release", clock)
        sup.pending = {"scripts/serve.py"}
        sup.app_pending = True
        sup.app_quiet_since = clock.now - 10
        touch_activity(sup.root, clock.now)
        error = run(sup._check_files) + run(sup._check_app)
        check(
            restarts == [] and builds == [] and sup.app_pending,
            "a change holds the restart and the app build together at the start" + error,
        )

        clock.now = NOW + serve_module.HOLD_CAP_SECONDS
        touch_activity(sup.root, clock.now)  # still changing: only the cap can release it
        error = run(sup._check_files)
        check(restarts == [["scripts/serve.py"]], "the cap fires the restart" + error)
        error = run(sup._check_app)
        check(
            builds != [] and not sup.app_pending,
            "the app build goes on that same release, not a second two-hour hold" + error,
        )


def check_dispatch_marks_before_handler() -> None:
    """A state change marks activity before its handler runs, not only after it returns (D176).

    The body is withheld until the mark has landed. A mark that waits for the handler to finish
    cannot land in that window, because the handler is still reading the body.
    """
    print("\n  a state change marks activity before its handler runs, as well as after (D176)")
    with tempfile.TemporaryDirectory() as tmp:
        tree = build_tree(Path(tmp))
        port = PORTS[tree]
        serve(tree, "up")
        try:
            up = wait_until(lambda: get(port, "/status")[0] == 200)
            check(up, "the capture server comes up")
            body = json.dumps({"name": "Mid-write probe"}).encode("utf-8")
            before = activity_mtime(tree)
            with socket.create_connection(("127.0.0.1", port), timeout=10) as wire:
                wire.sendall(
                    (f"POST /boxes HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                     "Content-Type: application/json\r\n"
                     f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode("ascii")
                )
                marked = wait_until(
                    lambda: activity_mtime(tree) not in (None, before), seconds=5,
                )
                check(
                    marked,
                    "a POST whose body has not arrived has already marked activity",
                )
                wire.sendall(body)
                reply = b""
                with contextlib.suppress(OSError):
                    for chunk in iter(lambda: wire.recv(4096), b""):
                        reply += chunk
            status = reply.split(b" ", 2)
            check(
                len(status) > 1 and status[1].startswith(b"2"),
                "and the POST completes once its body arrives",
            )
        finally:
            serve(tree, "down", "--confirm")


def check_stale_skip_file() -> None:
    print("\n  a skip file armed before this hold began does not release it (D176)")
    clock = FakeClock(NOW)
    with tempfile.TemporaryDirectory() as tmp, swapped(serve_module, time=clock):
        sup, restarts = idle_supervisor(Path(tmp) / "stale-skip", clock)
        skip = sup.root / ".serve" / "restart-now"
        skip.write_text("", "utf-8")
        os.utime(skip, (NOW - 200, NOW - 200))  # armed before the hold below began
        sup.held_since = NOW - 100
        touch_activity(sup.root, clock.now - 10)  # a change 10 s old: the hold must stand
        sup.pending = {"scripts/serve.py"}
        error = run(sup._check_files)
        check(
            restarts == [] and "scripts/serve.py" in sup.pending,
            "a skip file older than the hold does not fire it, and the change stays pending"
            + error,
        )

        skip.write_text("", "utf-8")  # armed again, inside the hold: this one counts
        os.utime(skip, (NOW - 5, NOW - 5))
        error = run(sup._check_files)
        check(
            restarts == [["scripts/serve.py"]] and not skip.exists(),
            "a skip file armed during the hold fires it, and is removed once it has" + error,
        )


def check_restart_now_lever() -> None:
    """The lever the owner runs. Its target and its state folder are swapped for a sandbox, so
    the case cannot reach the owner's primary checkout whatever this file does."""
    print("\n  the restart-now lever writes its skip file only while a restart waits (D176)")
    with tempfile.TemporaryDirectory() as tmp:
        primary = Path(tmp) / "primary"
        state = primary / ".serve"
        skip = state / serve_module.SKIP_FILE

        def lever() -> None:
            with swapped_or_absent(
                serve_module,
                restart_target=lambda root=None: primary,
                state_dir=lambda root=None: state,
            ), contextlib.redirect_stdout(io.StringIO()):
                serve_module.do_restart_now(argparse.Namespace())

        error = run(lever)
        check(
            not skip.exists(),
            "nothing waits: the lever writes no skip file, so no later hold is released by it"
            + error,
        )

        state.mkdir(parents=True, exist_ok=True)
        (state / serve_module.WAITING_FILE).write_text(f"{NOW}\n", "utf-8")
        skip.unlink(missing_ok=True)
        error = run(lever)
        check(skip.exists(), "a restart waits: the lever writes the skip file" + error)


def check_restart_target_from_linked_worktree() -> None:
    print("\n  restart_target from a linked worktree names the primary checkout (D176)")
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env["BANCHI_MAIN"] = "off"

    def git(where: Path, *argv: str) -> None:
        subprocess.run(  # noqa: S603
            ["git", "-c", "user.email=selftest@example.com", "-c", "user.name=selftest",
             "-c", "commit.gpgsign=false", *argv],
            cwd=str(where), env=env, capture_output=True, text=True, check=False,
        )

    with tempfile.TemporaryDirectory() as tmp:
        primary = Path(tmp) / "primary"
        linked = Path(tmp) / "linked"
        primary.mkdir()
        git(primary, "init", "-q", "-b", "main")
        git(primary, "commit", "-q", "--no-verify", "--allow-empty", "-m", "main")
        git(primary, "worktree", "add", "-q", "-b", "linked-branch", str(linked))

        answer: list = []
        error = run(lambda: answer.append(serve_module.restart_target(linked)))
        check(
            bool(answer) and Path(answer[0]).resolve() == primary.resolve(),
            "from a linked worktree the target is the primary checkout, whose supervisor "
            "serves :8000, not the linked tree's own `.serve/`" + error,
        )


def main() -> int:
    print("supervisor self-test — the build job, against a throwaway tree (D138)")
    check_port_split()
    check_idle_restart()
    check_child_marks_activity()
    check_cap_releases_build()
    check_dispatch_marks_before_handler()
    check_stale_skip_file()
    check_restart_now_lever()
    check_restart_target_from_linked_worktree()
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        tree = build_tree(where)
        port = PORTS[tree]

        # ------------------------------------------------------ a cold start builds first
        print("\n  a cold tree builds before the port opens")
        started = serve(tree, "up")
        try:
            up = wait_until(lambda: get(port, "/status")[0] == 200)
            check(up, "the capture server comes up")
            status, body = get(port, "/")
            check(
                status == 200 and b"Banchi" in body,
                "and `GET /` ALREADY answers with a build — nothing was served before it "
                "existed, which is what makes the cold case block rather than show a page",
            )
            check(
                "building the app before opening the port" in supervisor_log(tree),
                "the log says why it waited",
            )
            check(
                "banchi    http://" in started.stdout,
                "`make up` prints ONE link and it is the capture port",
            )
            check(
                ":5173" not in started.stdout and "app       http" not in started.stdout,
                "and no second link — there is no second server to name",
            )
            state = report(tree)
            check(
                state.get("app_built") is True and state.get("app_stale") is False,
                "`make status` reads a current build",
            )
            check(
                state.get("app_build_verdict") == "pass",
                "and the verdict file says pass",
            )

            # ------------------------------------------------------- an edit rebuilds once
            print("\n  a screen edit rebuilds, and restarts nothing")
            capture_pid = state.get("capture_pid")
            (tree / "app" / "generation").write_text("2\n", "utf-8")
            (tree / "app" / "src" / "App.tsx").write_text(
                "export default function App() { return null }\n", "utf-8"
            )
            rebuilt = wait_until(lambda: b"2" in get(port, "/assets/main-aaaa.js")[1])
            check(rebuilt, "the new bundle is being served")
            after = report(tree)
            check(
                after.get("capture_pid") == capture_pid,
                "AND THE CAPTURE CHILD DID NOT RESTART — the two watch sets are separate on "
                "purpose, so a `.tsx` save never bounces the server a rig is capturing with",
            )
            check(
                after.get("app_stale") is False,
                "the stamp advanced, so the build does not fire again",
            )
            quiet = supervisor_log(tree).count("app source changed")
            time.sleep(2.5)
            check(
                supervisor_log(tree).count("app source changed") == quiet,
                "and it stays quiet: a build that scheduled itself would loop forever",
            )

            # --------------------------------------------------- a failed build changes nothing
            print("\n  a failed build leaves the last bundle exactly where it was")
            before = get(port, "/assets/main-aaaa.js")[1]
            serve(tree, "down", "--confirm")
            wait_until(lambda: get(port, "/status")[0] == 0, seconds=60)
            (tree / "app" / "generation").write_text("3\n", "utf-8")
            (tree / "app" / "src" / "App.tsx").write_text("// broken\n", "utf-8")
            serve(tree, "up", env={"SELFTEST_BUILD": "fail"})
            wait_until(lambda: get(port, "/status")[0] == 200)
            wait_until(lambda: report(tree).get("app_build_verdict") == "fail", seconds=60)
            state = report(tree)
            check(state.get("app_build_verdict") == "fail", "the verdict says fail")
            check(
                (state.get("app_build_detail") or "").startswith("error TS1005"),
                "carrying the first line of what went wrong, which is what `make status` "
                "shows instead of sending the operator to a log",
            )
            check(
                get(port, "/assets/main-aaaa.js")[1] == before,
                "AND THE PREVIOUS BUNDLE IS BYTE-IDENTICAL — a build is never made in place, "
                "so a compile error can never take the app off the air",
            )
            check(
                get(port, "/status")[0] == 200,
                "and the API is up regardless: a TypeScript error may not stop this server "
                "handing out cards",
            )
            check(
                not (tree / "app" / "dist.next").exists(),
                "the half-built directory is removed, so the next build is not refused by it",
            )

            # ------------------------------------- the old bundle serves DURING a slow build
            print("\n  a build in flight serves the old bundle throughout")
            serve(tree, "down", "--confirm")
            wait_until(lambda: get(port, "/status")[0] == 0, seconds=60)
            (tree / "app" / "generation").write_text("4\n", "utf-8")
            serve(tree, "up", env={"SELFTEST_BUILD_SLEEP": "3"})
            wait_until(lambda: get(port, "/status")[0] == 200, seconds=60)
            (tree / "app" / "generation").write_text("5\n", "utf-8")
            (tree / "app" / "src" / "App.tsx").write_text("// five\n", "utf-8")
            seen = set()
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                code, body = get(port, "/assets/main-aaaa.js")
                seen.add((code, b"5" in body))
                if (200, True) in seen:
                    break
                time.sleep(0.2)
            check(
                all(code == 200 for code, _ in seen),
                "every request during the build answered 200 — the swap is two renames, so "
                "there is no window in which `dist/` is empty",
            )
            check((200, True) in seen, "and the new bundle lands when the build finishes")
            # THE LOOP ABOVE CAN EXIT ON THE STARTUP BUILD, not the edit's. That build reads
            # `generation` when it ends, so it can serve "5" while the `.tsx` edit is still owed
            # its own build; and a bundle serves BEFORE its build logs "app built in". Count
            # builds from there and the owed build lands inside the next step's window, and is
            # read as a server edit rebuilding. So wait for the bundle to be current AND for the
            # last build the log started to have logged its finish.
            check(
                wait_until(
                    lambda: report(tree).get("app_stale") is False and build_logged(tree),
                    seconds=60,
                ),
                "and every build owed to that edit has finished and said so, so the next step "
                "starts from a settled baseline",
            )

            # ------------------------------------------------- a python edit is the other track
            print("\n  a Python edit restarts the server and does not build")
            builds = supervisor_log(tree).count("app built in")
            edit_mark = len(supervisor_log(tree))
            pid_before = report(tree).get("capture_pid")
            marker = tree / "server" / "ports.py"
            marker.write_text(marker.read_text("utf-8") + "\n# selftest\n", "utf-8")
            changed = wait_until(
                lambda: report(tree).get("capture_pid") not in (None, pid_before), seconds=60
            )
            check(changed, "the capture child restarts for a Python change")
            # A REBUILD AFTER A RESTART IS LOGGED JUST AFTER "capture server ready", and a pid
            # change alone is read before either. So a server edit that DID rebuild passed this
            # check. Wait for the restarted child to be ready, and for any build that then
            # started (its "rebuilding" line) to have logged its finish.
            def restart_settled() -> bool:
                since = supervisor_log(tree)[edit_mark:]
                return "capture server ready" in since and since.rfind("app built in") >= since.rfind(
                    "rebuilding"
                )

            check(
                wait_until(restart_settled, seconds=60),
                "and the restart has run to the end, so the count below cannot read too early",
            )
            check(
                supervisor_log(tree).count("app built in") == builds,
                "AND NOTHING WAS REBUILT — the reverse of the arm above, and the pair is what "
                "keeps a screen edit and a server edit from ever triggering each other",
            )
        finally:
            serve(tree, "down", "--confirm")
            wait_until(lambda: get(port, "/status")[0] == 0, seconds=60)

        # --------------------------------------------------- no node at all on PATH
        # THE FAILURE D138's PLIST SECTION ALREADY NAMES, and the one that separates the two
        # halves of this process: launchd hands an agent a minimal PATH, `npx` is routinely
        # not on it, and the app half then cannot build while the API half is perfectly fine.
        # A missing `node_modules` is deliberately NOT the case tested here — with a lockfile
        # present the supervisor runs `npm ci` and fixes it, which is the owner's own ruling.
        print("\n  the app half can fail while the API half does not")
        second = where / "second"
        second.mkdir()
        tree2 = build_tree(second)
        (second / "bin" / "npx").unlink()
        (second / "bin" / "npm").unlink()
        port2 = PORTS[tree2]
        # A PATH WITH PYTHON ON IT AND NO NODE, BUILT RATHER THAN TYPED. The first version of
        # this was `/usr/bin:/bin`, which is where macOS keeps python3 and is NOT where the
        # Ubuntu CI runner keeps it — the throwaway tree has no `.venv`, so
        # `serve.python_executable` returns a bare "python3" resolved off PATH, and with that
        # PATH the CAPTURE SERVER could not start either. Two arms failed on CI and passed
        # here, which is the "a green check proves its own platform" trap exactly.
        minimal = os.pathsep.join(
            [str(second / "bin"), str(Path(sys.executable).parent), "/usr/bin", "/bin"]
        )
        # AND THE TEST CHECKS ITS OWN PREMISE, because a PATH that accidentally still had node
        # on it would make every assertion below pass while proving nothing. If a platform ever
        # ships node beside python, this says so instead of going quietly green.
        check(
            shutil.which("npx", path=minimal) is None,
            "the minimal PATH genuinely has no node on it",
        )
        check(
            shutil.which("python3", path=minimal) is not None
            or Path(sys.executable).name.startswith("python"),
            "and still has python, which the supervisor needs to spawn the capture server",
        )
        serve(tree2, "up", env={"PATH": minimal})
        try:
            wait_until(lambda: get(port2, "/status")[0] == 200, seconds=60)
            check(get(port2, "/status")[0] == 200, "with no node on PATH the API still comes up")
            status, _ = get(port2, "/")
            check(
                status == 503,
                "and `GET /` is 503 — the app is not missing, it is not ready, and the "
                "operator is told which",
            )
            state = report(tree2)
            check(
                state.get("app_build_verdict") in ("fail", "install-failed"),
                "the verdict records a failure rather than a silent absence",
            )
            check(
                "not found" in (state.get("app_build_detail") or ""),
                "naming the missing program, not a compile error it never got to",
            )
            check(
                "launch-agent" in supervisor_log(tree2),
                "and the log points at the one thing that fixes it — a launchd PATH with no "
                "node on it is the documented cause and the operator should not have to guess",
            )
        finally:
            serve(tree2, "down", "--confirm", env={"PATH": minimal})
            wait_until(lambda: get(port2, "/status")[0] == 0, seconds=60)

    # ---------------------------------------------------------------------------------
    # THE PRIMARY CHECKOUT SERVES MAIN (D158). Its own tree, its own port, its own git.
    with tempfile.TemporaryDirectory() as tmp3:
        where3 = Path(tmp3)
        tree3 = build_tree(where3)
        port3 = PORTS[tree3]
        make_primary_checkout(tree3)
        print()
        print("  -- D158: the rig refuses to serve a primary checkout that is off main --")

        serve(tree3, "up")
        try:
            up = wait_until(lambda: get(port3, "/status")[0] == 200, seconds=60)
            check(up, "on main, a primary checkout serves exactly as it always did")

            # THE OBSERVED INCIDENT, REPRODUCED. Both times this happened the supervisor was
            # already alive and the tree moved under it.
            git_switch(tree3, "feature")
            stood = wait_until(
                lambda: "NOT SERVING" in supervisor_log(tree3), seconds=30)
            check(stood, "a branch switch under a live supervisor is REFUSED, not adopted")
            check(
                "feature" in supervisor_log(tree3),
                "and the refusal names the branch, which is the fact nothing printed twice",
            )
            check(
                get(port3, "/status")[0] == 200,
                "the server that was already running is STILL ANSWERING — the guard refuses "
                "an adoption and never stops a capture in flight",
            )

            # AND IT COMES BACK WITH NOTHING TYPED, which is what keeps this from being the
            # guard somebody switches off.
            before = supervisor_log(tree3)
            git_switch(tree3, "main")
            check(
                wait_until(lambda: "back on main" in supervisor_log(tree3)[len(before):],
                           seconds=30),
                "switching back to main resumes serving by itself",
            )

            # THE RE-EXEC ARM. This branch's own scripts/serve.py has the guard deleted, so a
            # supervisor that checked the branch AFTER exec'ing into it would sail through.
            mark = len(supervisor_log(tree3))
            git_switch(tree3, "no-guard")
            check(
                wait_until(lambda: "NOT SERVING" in supervisor_log(tree3)[mark:], seconds=30),
                "a branch whose own serve.py deletes the guard is refused BEFORE the re-exec "
                "— the running image decides, so a branch cannot ship the code that lets it in",
            )
            check(
                "restarting MYSELF" not in supervisor_log(tree3)[mark:],
                "and the supervisor did not re-exec at all",
            )
            git_switch(tree3, "main")
            wait_until(lambda: get(port3, "/status")[0] == 200, seconds=60)

            # THE APP HALF, WHICH IS A SECOND PATH AND NOT A SECOND SPELLING OF THE FIRST.
            # This branch moves nothing the capture server imports, so `_restart_for` is never
            # called at all — and since D138 the bundle is what a person actually looks at.
            mark = len(supervisor_log(tree3))
            git_switch(tree3, "app-only")
            check(
                wait_until(lambda: "NOT SERVING" in supervisor_log(tree3)[mark:], seconds=30),
                "a branch that moves ONLY app/src is refused too — the bundle is code as much "
                "as the server is",
            )
            check(
                "rebuilding" not in supervisor_log(tree3)[mark:],
                "and no build was run, so the bundle being served is still main's",
            )
            git_switch(tree3, "main")
        finally:
            serve(tree3, "down", "--confirm")
            wait_until(lambda: get(port3, "/status")[0] == 0, seconds=60)

        # A COLD START IS THE OTHER HALF, and it is the shape the second incident was in: the
        # tree was left on a merged branch and a login would have served it.
        git_switch(tree3, "feature")
        done = serve(tree3, "up")
        check(done.returncode == 1, "`make up` on a branch REFUSES, and says so in its status")
        check("NOT SERVING" in done.stdout, "naming itself rather than failing on a timeout")
        check(
            get(port3, "/status")[0] == 0,
            "and nothing is listening — a cold start on a branch serves nothing at all",
        )
        check(
            "BANCHI_SERVE_MAIN=off" in done.stdout,
            "the refusal prints its escape hatch, as every refusal in this repo does",
        )

        # AND THE LOGIN PATH, WHICH IS NOT `make up`. `make launch-agent` writes a plist whose
        # ProgramArguments are `[python, serve.py, run]` — it never goes through `do_up`, so
        # `do_up`'s preflight above is not the arm that covers a Mac booting with this tree
        # parked on a branch. That is `Supervisor.start()`, and this is its arm.
        log_before = len(supervisor_log(tree3))
        # STDOUT GOES TO THE LOG FILE, because that is what launchd does and because `log()` is
        # a `print`. Written with DEVNULL first, this arm went red for the one reason a reader
        # would never guess: the supervisor refused exactly as it should and every word of the
        # refusal went to /dev/null. The plist's `StandardOutPath` is this line.
        handle = open(  # noqa: SIM115 — the child's stdout, closed in the finally below
            tree3 / ".serve" / "supervisor.log", "a", buffering=1, encoding="utf-8")
        child = subprocess.Popen(  # noqa: S603
            [sys.executable, str(tree3 / "scripts" / "serve.py"), "run"],
            cwd=str(tree3), env=serve_env(tree3),
            stdin=subprocess.DEVNULL, stdout=handle,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        try:
            check(
                wait_until(lambda: "NOT SERVING" in supervisor_log(tree3)[log_before:],
                           seconds=30),
                "a supervisor started the way launchd starts it REFUSES a tree parked on a "
                "branch — the second incident's shape, where the tree was left on a merged one",
            )
            check(
                get(port3, "/status")[0] == 0,
                "and no port was ever opened, so nothing can answer for the real store",
            )
            check(
                child.poll() is None,
                "the supervisor STAYS ALIVE rather than exiting — launchd's KeepAlive restarts "
                "an unsuccessful exit, so exiting would be this refusal on a ten-second loop",
            )
            git_switch(tree3, "main")
            check(
                wait_until(lambda: get(port3, "/status")[0] == 200, seconds=60),
                "and `git switch main` brings the rig up with nothing else typed",
            )
        finally:
            serve(tree3, "down", "--confirm")
            wait_until(lambda: get(port3, "/status")[0] == 0, seconds=60)
            if child.poll() is None:
                child.terminate()
            handle.close()
        git_switch(tree3, "feature")

        # THE HATCH IS REAL, and it has to be: serving a branch against the real camera and the
        # real store is a thing the owner may legitimately want, and no other command does it.
        serve(tree3, "up", env={"BANCHI_SERVE_MAIN": "off"})
        try:
            check(
                wait_until(lambda: get(port3, "/status")[0] == 200, seconds=60),
                "BANCHI_SERVE_MAIN=off serves the branch anyway",
            )
        finally:
            serve(tree3, "down", "--confirm", env={"BANCHI_SERVE_MAIN": "off"})
            wait_until(lambda: get(port3, "/status")[0] == 0, seconds=60)

    # ------------------------------------- AND THE REFUSAL IS THE FALLBACK, NOT THE ANSWER
    #
    # D176. Every arm above proves the supervisor REFUSES a tree
    # it must not serve, and all of them are still right — because their fixture has no origin
    # to sync to. This one gives it one, parks the tree on a branch, and starts a supervisor the
    # way launchd does: the rig must come UP, on main, at origin/main, with nothing typed.
    #
    # IT IS THE END-TO-END SHAPE AND NOT A SECOND UNIT TEST. `scripts/sync-selftest.py` owns the
    # states and the refusals; what only this fixture can show is that a real supervisor, in a
    # real checkout, reaches the sync at an adoption moment and then goes on to serve.
    print("\n  a parked tree with an origin SYNCS ITSELF and then serves")
    with tempfile.TemporaryDirectory() as tmp5:
        where5 = Path(tmp5)
        tree5 = build_tree(where5)
        port5 = PORTS[tree5]
        make_primary_checkout(tree5)
        give_origin(tree5)
        git_switch(tree5, "feature")
        behind = subprocess.run(  # noqa: S603, S607
            ["git", "rev-parse", "refs/remotes/origin/main"], cwd=str(tree5),
            capture_output=True, text=True, check=False).stdout.strip()

        started5 = serve(tree5, "up")
        try:
            check(
                wait_until(lambda: get(port5, "/status")[0] == 200, seconds=60),
                "the rig COMES UP from a tree parked on a branch — the refusal was the "
                "fallback, and the sync is the answer",
            )
            on = subprocess.run(  # noqa: S603, S607
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(tree5),
                capture_output=True, text=True, check=False).stdout.strip()
            check(on == "main", "PART 1: the tree it is serving is on main")
            now = subprocess.run(  # noqa: S603, S607
                ["git", "rev-parse", "refs/heads/main"], cwd=str(tree5),
                capture_output=True, text=True, check=False).stdout.strip()
            check(
                now == behind and now != "",
                "PART 2: and main is at origin/main, so the code being served is current",
            )
            # NOT SILENT, ASSERTED AGAINST THE STREAM THE READER IS ACTUALLY ON. `do_up` runs
            # the sync in the foreground and PRINTS — a person typed `make up` and is watching
            # that terminal — so this is `up`'s own stdout and not the supervisor log. The
            # first draft of this arm ended in `or True`, which is the vacuous green
            # docs/debts/ opens by warning about: it would have passed against a sync that
            # said nothing at all.
            check(
                "primary-sync:" in started5.stdout and "-> main" in started5.stdout,
                "and it SAYS what it did, on the stream the person who typed `make up` is "
                "reading, naming both parts",
            )
            check(
                started5.returncode == 0,
                "with a zero status, because the rig came up — the refusal's 1 is gone",
            )
            report5 = report(tree5)
            check(
                report5.get("off_main") is None,
                "`make status` reports no stand-down, because there is nothing to stand down "
                "from any more",
            )
        finally:
            serve(tree5, "down", "--confirm")
            wait_until(lambda: get(port5, "/status")[0] == 0, seconds=60)

        # AND THE DIRTY CASE END TO END: a tracked edit in the parked tree must leave the rig
        # refusing rather than syncing, which is the one refusal the ruling names by hand.
        git_switch(tree5, "feature")
        watched = tree5 / "server" / "capture_server.py"
        watched.write_text(watched.read_text("utf-8") + "\n# uncommitted\n", "utf-8")
        refused5 = serve(tree5, "up")
        check(
            refused5.returncode == 1 and "NOT SERVING" in refused5.stdout,
            "a parked tree with UNCOMMITTED TRACKED WORK is still refused — the sync declines "
            "and the stand-down stands",
        )
        check(
            "capture_server.py" in refused5.stdout,
            "and the file holding it back is NAMED, which is the whole use of the refusal",
        )
        check(
            get(port5, "/status")[0] == 0,
            "nothing was served, and nothing was switched out from under the edit",
        )

    # A LINKED WORKTREE IS NOT THE SUBJECT AND MUST NOT BE CAUGHT (D43). Its `.git` is a FILE,
    # which is the one fact the whole test turns on and the one most likely to be written
    # backwards — `main` is a real branch in the parent, so silence here can only come from the
    # primary/linked test rather than from the gate beside it.
    with tempfile.TemporaryDirectory() as tmp4:
        where4 = Path(tmp4)
        tree4 = build_tree(where4)
        make_primary_checkout(tree4)
        linked = where4 / "linked"
        subprocess.run(  # noqa: S603, S607
            ["git", "worktree", "add", "-q", "-b", "wt", str(linked), "feature"],
            cwd=str(tree4), env=dict(os.environ, BANCHI_MAIN="off"),
            capture_output=True, text=True, check=False,
        )
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_serve_under_test", tree4 / "scripts" / "serve.py")
        under_test = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(under_test)
        check(
            under_test.off_main(linked) is None,
            "a LINKED worktree standing on a branch is not the subject and is silent",
        )
        check(
            under_test.off_main(tree4) is None,
            "and the primary checkout beside it, on main, is silent too",
        )

        # THREE ANSWERS NO SERVER-LEVEL ARM CAN REACH, and every one of them survived the
        # mutation sweep until it was written. They are asked of the function directly because
        # each needs a repository in a state the end-to-end fixture cannot also be in.
        git_switch(tree4, "feature")
        check(
            under_test.off_main(tree4) == "feature",
            "the primary checkout on a branch names the branch",
        )
        subprocess.run(["git", "pack-refs", "--all"], cwd=str(tree4),  # noqa: S603, S607
                       env=dict(os.environ, BANCHI_MAIN="off"),
                       capture_output=True, check=False)
        check(
            not (tree4 / ".git" / "refs" / "heads" / "main").exists(),
            "`git pack-refs` really did move main out of refs/heads — the setup for the next "
            "one, asserted because a case that silently failed to pack would prove nothing",
        )
        check(
            under_test.off_main(tree4) == "feature",
            "and main is still FOUND once git has packed it away — a loose-refs-only reader "
            "would go quiet the first time `git gc` ran on the rig",
        )
        subprocess.run(["git", "switch", "-q", "--detach", "main"],  # noqa: S603, S607
                       cwd=str(tree4), env=dict(os.environ, BANCHI_MAIN="off"),
                       capture_output=True, check=False)
        detached = under_test.off_main(tree4)
        check(
            detached is not None and "detached HEAD" in detached,
            "a detached HEAD is off main as surely as a branch is, and is NAMED as one rather "
            "than reported as a branch called HEAD",
        )

        # AND A REPOSITORY THAT DOES NOT CALL ITS TRUNK `main` IS NOT IN VIOLATION. The fixture
        # above cannot make this case — `main` exists there by construction — which is exactly
        # why the gate went unnoticed by every other arm.
        foreign = where4 / "foreign"
        foreign.mkdir()
        fenv = dict(os.environ, BANCHI_MAIN="off")
        for argv in (["init", "-q", "-b", "master"],
                     ["config", "user.email", "selftest@example.com"],
                     ["config", "user.name", "selftest"],
                     ["config", "commit.gpgsign", "false"]):
            subprocess.run(["git", *argv], cwd=str(foreign), env=fenv,  # noqa: S603, S607
                           capture_output=True, check=False)
        (foreign / "f.txt").write_text("one", "utf-8")
        for argv in (["add", "-A"], ["commit", "-qm", "seed"], ["switch", "-q", "-c", "topic"]):
            subprocess.run(["git", *argv], cwd=str(foreign), env=fenv,  # noqa: S603, S607
                           capture_output=True, check=False)
        check(
            under_test.off_main(foreign) is None,
            "a checkout whose trunk is called something else is not in violation for it",
        )

    print()
    if failures:
        print(f"{FAIL}  {len(failures)} of the supervisor's build behaviours are wrong")
        for line in failures:
            print(f"       {line}")
        return 1
    print(f"{PASS}  the supervisor builds, swaps and refuses as D138 says it does")
    return 0


if __name__ == "__main__":
    sys.exit(main())
