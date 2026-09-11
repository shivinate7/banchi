#!/usr/bin/env python3
"""The supervisor's build job, proved against a throwaway tree (D135).

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

THE PORT IS PINNED WITH `PKMNSCAN_PORT`, AND THE OBVIOUS ALTERNATIVE IS A BUG. Letting the copy
derive its own looks right — that is what D43 does for every tree — but the derivation asks
whether the directory is a LINKED WORKTREE, and a `shutil.copytree` of this repo is not one. So
the copy calls itself the main checkout and claims :8000, which on the owner's Mac is their live
capture server over their real store. Measured, the first time this script was run: `up` in the
copy refused with ":8000 is already held". Pinned to a free socket the OS hands out instead.

IN `make check`, NEVER IN THE GIT HOOK. D18: it writes, and nothing that writes may gate a
commit. Same placement and same reason as `audit-self-test`, `githooks-selftest`,
`merge-selftest`, `janitor-selftest` and `verdict-selftest`.
"""

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

# What a copy needs to run a supervisor and a capture server. `app/` is NOT copied — the tree
# gets a stub one, because a real `app/` means `node_modules` and a real `vite build`, which is
# the one thing this script is deliberately not testing.
CARRY = (
    "scripts/serve.py",
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


def free_port() -> int:
    """A port the OS says is free right now. Bound, read, released — the standard idiom, and
    the small race it carries is the right trade against a hard-coded number that would make
    two runs of this script collide."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def serve(tree: Path, *args: str, env: Optional[dict] = None, timeout: int = 120):
    child_env = dict(os.environ)
    child_env["PKMNSCAN_HOME"] = str(tree / "home")
    child_env["PKMNSCAN_PORT"] = str(PORTS[tree])
    child_env["PATH"] = f"{tree.parent / 'bin'}{os.pathsep}{child_env.get('PATH', '')}"
    child_env.update(env or {})
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


def supervisor_log(tree: Path) -> str:
    try:
        return (tree / ".serve" / "supervisor.log").read_text("utf-8")
    except OSError:
        return ""


def main() -> int:
    print("supervisor self-test — the build job, against a throwaway tree (D135)")
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

            # ------------------------------------------------- a python edit is the other track
            print("\n  a Python edit restarts the server and does not build")
            builds = supervisor_log(tree).count("app built in")
            pid_before = report(tree).get("capture_pid")
            marker = tree / "server" / "ports.py"
            marker.write_text(marker.read_text("utf-8") + "\n# selftest\n", "utf-8")
            changed = wait_until(
                lambda: report(tree).get("capture_pid") not in (None, pid_before), seconds=60
            )
            check(changed, "the capture child restarts for a Python change")
            check(
                supervisor_log(tree).count("app built in") == builds,
                "AND NOTHING WAS REBUILT — the reverse of the arm above, and the pair is what "
                "keeps a screen edit and a server edit from ever triggering each other",
            )
        finally:
            serve(tree, "down", "--confirm")
            wait_until(lambda: get(port, "/status")[0] == 0, seconds=60)

        # --------------------------------------------------- no node at all on PATH
        # THE FAILURE D53's PLIST SECTION ALREADY NAMES, and the one that separates the two
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

    print()
    if failures:
        print(f"{FAIL}  {len(failures)} of the supervisor's build behaviours are wrong")
        for line in failures:
            print(f"       {line}")
        return 1
    print(f"{PASS}  the supervisor builds, swaps and refuses as D135 says it does")
    return 0


if __name__ == "__main__":
    sys.exit(main())
