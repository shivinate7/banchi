#!/usr/bin/env python3
"""ONE BROWSER FLEET AT A TIME ON THIS MACHINE.

D43 gave every checkout its own dev port, its own capture port and its own store, so two
trees can be worked in at once without either answering for the other. **The machine's CPU
is the one resource it could not give them a copy of**, and `make design-check` is the one
target that consumes all of it: `app/playwright.config.ts` is `fullyParallel` with
Playwright's default worker count, which is half the cores — seven on this 15-core Mac —
each worker a Chromium context, plus a Vite dev server compiling the module graph for every
one of them.

WHAT TWO OF THOSE AT ONCE LOOKS LIKE, measured 2026-09-07 in the `magical-kalam-0230c3`
worktree while `cap-on-demand` ran its own suite — about 90 browser processes between them:

    18 failures, every one of them in shipping.spec.ts or run-panel.spec.ts, with the WHOLE
    of shipping failing rather than individual assertions. Re-run alone, nothing else
    touched: 52 passed.

Earlier in that same session the same collision produced ONE intermittent failure in
nav.spec.ts and one in capture-undo.spec.ts, each of which also passed in isolation. That is
the shape worth naming: a starved fleet does not report starvation, it reports whichever
assertion happened to be waiting when the frame never came, and every one of them costs a
re-run to disprove. Nothing anywhere said the other tree was the reason.

**THE REPO HAD ALREADY DIAGNOSED THE FAILURE AND COULD NOT SEE IT ACROSS TWO RUNS.**
`app/playwright.config.ts` records it against a deliberately starved rig — *"a context can
fail to render at all rather than slowly: with the allowance raised to 120s, 10 of 80 still
failed and one took 122s. A wait cannot answer that"* — and that comment is about
oversubscription WITHIN one run, where the config can at least count its own workers. Across
two runs in two checkouts there is nothing to count with, which is what this file supplies.

WHAT IS NOT THE CAUSE, so nobody re-derives it: the capture server. `app/tests/shell.ts`'s
`sealEveryTest` aborts every capture request, and D43 gives each checkout its own capture
port, so two suites never touch one server. The contention is CPU and memory and nothing
else — which is also why the lock is machine-wide rather than per-checkout, and why it must
live outside every checkout.

WHY `flock` AND NOT A PIDFILE. `scripts/serve.py` proves a pid is still the process it
recorded by comparing `ps -o command=` against the argv it stored, and it has to: a port is
the resource there, and a port outlives the process that held it in exactly the states that
matter. Here the OS can own the whole question — an advisory lock is released when the
holder exits, however it exits, including `kill -9`, a crashed session and a reboot. There
is no stale-lock path in this file because there is no stale lock. The pid, the tree and the
command are written INTO the locked file, and they are read for one purpose only: naming the
holder in the refusal.

WHY IT REFUSES RATHER THAN WAITS. A suite that silently waits for another tree looks hung,
which is its own failure mode and one the 2026-09-07 session also hit — it is ten minutes
before anybody suspects a queue. So the default is a refusal that names the tree holding the
lock, and `--wait` is the opt-in, which ANNOUNCES ITSELF on the first line and keeps saying
so every thirty seconds. Neither mode is silent about which tree it is behind.

THE REFUSAL EXITS 75, NOT 1. `playwright test` exits 1 when tests fail, and a guard against
false failures must not produce one: `make` prints `Error 75`, which is a number nothing
else here returns. 75 is EX_TEMPFAIL — "try again later" — which is precisely the claim.

    scripts/suite-lock.py run [--name NAME] [--wait [SECONDS]] -- <command …>
    scripts/suite-lock.py status [--name NAME]
    scripts/suite-lock.py selftest

Stdlib only, and `python3` rather than `$(PYTHON)` in the Makefile — same rule as `status`,
`docs-audit` and `checks`. A guard that needs `make venv` before it can refuse is a guard a
fresh worktree runs without.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The lock's home, and the one thing about this file that may not be per-checkout. `.serve/`
#: would put it inside the tree, which is the whole defect — two trees would take two locks
#: and agree with each other about nothing. `~` because the contention is between the
#: processes of one user on one machine, which is what a home directory already scopes.
DEFAULT_LOCK_DIR = Path.home() / ".pkmnscan" / "locks"

#: Overridden only by the self-test, which must not touch the real lock while a real suite may
#: be holding it. Same shape as `scripts/janitor.py --sessions DIR`, for the same reason.
LOCK_DIR_ENV = "PKMNSCAN_LOCK_DIR"

#: The escape hatch, in the shape `PKMNSCAN_MAIN=off` and `PKMNSCAN_FOREGROUND=ok` already
#: use, and printed in every refusal. A guard with no visible way past it gets disarmed
#: somewhere worse — by deleting the line from the Makefile, which nothing would catch.
ESCAPE_ENV = "PKMNSCAN_SUITE_LOCK"

#: What the refusal exits with. See the module docstring: `1` is what a failing suite exits
#: with, and this must never be mistaken for one.
BUSY = 75

#: The default lock. Named for the RESOURCE rather than for `design-check`, so the second
#: browser fleet to land here joins this lock instead of inventing a second one that does not
#: exclude the first.
DEFAULT_NAME = "browsers"

#: `--wait` with no figure. Long enough to outlast a full suite in the other tree (461 tests
#: at seven workers) and short enough that a wait which is never going to end still ends.
DEFAULT_WAIT_SECONDS = 1800

#: How often a wait says it is still waiting. The first line is printed immediately; this is
#: what keeps a ten-minute queue from reading as a hang.
HEARTBEAT_SECONDS = 30

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def lock_dir() -> Path:
    override = os.environ.get(LOCK_DIR_ENV, "").strip()
    return Path(override) if override else DEFAULT_LOCK_DIR


def lock_path(name: str) -> Path:
    return lock_dir() / f"{name}.lock"


def bypassed() -> bool:
    return os.environ.get(ESCAPE_ENV, "").strip().lower() in ("off", "0", "no")


def elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}m{seconds % 60:02d}s"


def read_record(path: Path) -> Optional[dict]:
    """Whatever the holder wrote, or None.

    ONLY EVER CALLED AFTER `flock` HAS ALREADY REFUSED, so "somebody holds it" is settled
    before this runs and a None here narrows nothing — it means the record is not readable
    YET. The holder takes the lock and then writes, so there is a window of a few
    microseconds in which the file is empty and genuinely locked. The refusal says so rather
    than inventing a holder.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def describe(record: Optional[dict]) -> List[str]:
    """The holder, as lines for a refusal. Never raises: this runs on the error path."""
    if not record:
        return ["  held by another run — it had not written its record yet."]
    lines = []
    tree = record.get("tree")
    pid = record.get("pid")
    if tree:
        lines.append(f"  tree      {tree}")
    if isinstance(pid, int):
        lines.append(f"  pid       {pid}")
    started = record.get("started_at")
    if isinstance(started, (int, float)):
        lines.append(f"  running   {elapsed(time.time() - started)}")
    command = record.get("command")
    if command:
        lines.append(f"  command   {command}")
    return lines or ["  held by another run, which wrote a record this cannot read."]


def refuse(name: str, path: Path, record: Optional[dict], waited: float = 0.0) -> int:
    print(f"another {name} suite is running on this machine.")
    print()
    for line in describe(record):
        print(line)
    print()
    if waited:
        print(f"  waited {elapsed(waited)} and it is still running.")
        print()
    print("  Two Playwright fleets at once starve each other and BOTH report failures that")
    print("  are not in the code — 18 of them on 2026-09-07, all green on a re-run.")
    print()
    print("  make design-check ARGS=--wait")
    print("      queue behind it instead of refusing, and say so while waiting")
    print(f"  python3 scripts/suite-lock.py status --name {name}")
    print("      who holds it, asked of the lock rather than of a pid")
    print(f"  {ESCAPE_ENV}=off make design-check")
    print("      run anyway — and read whatever it reports knowing the above")
    print()
    print(f"  lock  {path}")
    return BUSY


class Lock:
    """An exclusive advisory lock on a file outside every checkout.

    The fd is held for the life of the process and never closed on the success path — closing
    it IS releasing the lock, so there is exactly one place that can happen and it is
    `release`. `LOCK_NB` throughout: the blocking form would make `--wait` unable to say
    anything while it waited, which is the failure mode `--wait` exists to avoid.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.path = lock_path(name)
        self.fd: Optional[int] = None

    def acquire(self, command: str) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.fd is None:
            self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                return False
            raise
        record = {
            "pid": os.getpid(),
            "tree": str(REPO_ROOT),
            "name": self.name,
            "command": command,
            "started_at": time.time(),
        }
        os.ftruncate(self.fd, 0)
        os.lseek(self.fd, 0, os.SEEK_SET)
        os.write(self.fd, json.dumps(record).encode("utf-8"))
        os.fsync(self.fd)
        return True

    def holder(self) -> Optional[dict]:
        return read_record(self.path)

    def release(self) -> None:
        """Clear the record, then drop the lock by closing the fd.

        CLOSING IS WHAT RELEASES — an explicit `LOCK_UN` beside it would be a line that never
        decides anything, and this file already argues that the OS owns the release. What
        `release` is actually FOR is the record: `status` reads it, and a file describing a
        holder that has gone is worse than one describing nobody. Proven by the self-test's
        `a finished run leaves no record`, which fails if this truncate is removed.
        """
        if self.fd is None:
            return
        with contextlib.suppress(OSError):
            os.ftruncate(self.fd, 0)
        with contextlib.suppress(OSError):
            os.close(self.fd)
        self.fd = None


def do_run(args: argparse.Namespace) -> int:
    command: List[str] = args.command
    if not command:
        print("suite-lock: nothing to run. Put the command after `--`.", file=sys.stderr)
        return 2
    if not _NAME_RE.match(args.name):
        print(f"suite-lock: `{args.name}` is not a lock name ([a-z0-9-]).", file=sys.stderr)
        return 2

    if bypassed():
        print(f"suite-lock: {ESCAPE_ENV}=off — running unguarded.", file=sys.stderr)
        return _spawn(command)

    lock = Lock(args.name)
    printable = " ".join(command)
    started = time.monotonic()
    if not lock.acquire(printable):
        if args.wait is None:
            return refuse(args.name, lock.path, lock.holder())
        deadline = started + args.wait
        record = lock.holder()
        print(f"waiting for the {args.name} suite lock — up to {elapsed(args.wait)}.")
        for line in describe(record):
            print(line)
        sys.stdout.flush()
        spoke = time.monotonic()
        while True:
            if time.monotonic() >= deadline:
                return refuse(args.name, lock.path, lock.holder(),
                              waited=time.monotonic() - started)
            time.sleep(0.5)
            if lock.acquire(printable):
                break
            if time.monotonic() - spoke >= HEARTBEAT_SECONDS:
                spoke = time.monotonic()
                print(f"  still waiting ({elapsed(time.monotonic() - started)}) …")
                sys.stdout.flush()
        print(f"  got it after {elapsed(time.monotonic() - started)}.")
        sys.stdout.flush()

    try:
        return _spawn(command)
    finally:
        lock.release()


def _spawn(command: List[str]) -> int:
    """Run it, and hand back its own exit code.

    NOT `exec`, because the lock dies with this process and an exec would drop it the moment
    the suite started. The child stays in this process group, so a Ctrl-C at a terminal
    reaches it directly — this process only has to survive long enough to release.
    """
    try:
        completed = subprocess.run(command)
    except FileNotFoundError:
        print(f"suite-lock: {command[0]}: not found", file=sys.stderr)
        return 127
    except KeyboardInterrupt:
        return 128 + signal.SIGINT
    if completed.returncode < 0:
        return 128 - completed.returncode
    return completed.returncode


def do_status(args: argparse.Namespace) -> int:
    lock = Lock(args.name)
    if not lock.path.exists():
        print(f"{args.name}: free (no lock file at {lock.path})")
        return 0
    # Ask the OS, not the record: taking the lock and dropping it again is the only
    # test of whether anybody holds it, and it is the same test `run` makes.
    probe = Lock(args.name)
    if probe.acquire("suite-lock status"):
        probe.release()
        print(f"{args.name}: free")
        return 0
    print(f"{args.name}: held")
    for line in describe(lock.holder()):
        print(line)
    return 0


# ------------------------------------------------------------------------------- self-test

def _selftest_run(lock_dir_path: Path, argv: List[str], env_extra: Optional[dict] = None,
                  timeout: int = 60) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env[LOCK_DIR_ENV] = str(lock_dir_path)
    env.pop(ESCAPE_ENV, None)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve())] + argv,
        capture_output=True, text=True, env=env, timeout=timeout,
    )


def do_selftest(_args: argparse.Namespace) -> int:
    """The guard, exercised by violating it.

    Every case here is one this file would otherwise be believed about rather than checked
    on. The last two are the ones worth having: a holder killed with -9 must leave the lock
    FREE, which is the entire argument for `flock` over a pidfile, and a suite's own exit
    code must survive the wrapper, or a red suite reads as green.
    """
    failures: List[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="suite-lock-selftest-"))
    holder: Optional[subprocess.Popen] = None

    def check(label: str, ok: bool, detail: str = "") -> None:
        if ok:
            print(f"  ok    {label}")
        else:
            print(f"  FAIL  {label}")
            if detail:
                print("\n".join(f"          {line}" for line in detail.splitlines()))
            failures.append(label)

    try:
        env = dict(os.environ)
        env[LOCK_DIR_ENV] = str(tmp)
        env.pop(ESCAPE_ENV, None)
        holder = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "run", "--", "sleep", "45"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        held = tmp / f"{DEFAULT_NAME}.lock"
        deadline = time.time() + 15
        while time.time() < deadline and not (held.exists() and held.stat().st_size):
            time.sleep(0.05)
        check("a run takes the lock", held.exists() and held.stat().st_size > 0)

        second = _selftest_run(tmp, ["run", "--", "true"])
        check("a second run is refused", second.returncode == BUSY,
              f"exit {second.returncode}\n{second.stdout}{second.stderr}")
        check("the refusal names the holding tree", str(REPO_ROOT) in second.stdout,
              second.stdout)
        check("the refusal names the escape hatch", ESCAPE_ENV in second.stdout, second.stdout)

        status = _selftest_run(tmp, ["status"])
        check("status reports it held", "held" in status.stdout, status.stdout)

        bypass = _selftest_run(tmp, ["run", "--", "true"], {ESCAPE_ENV: "off"})
        check("the escape hatch runs anyway", bypass.returncode == 0,
              f"exit {bypass.returncode}\n{bypass.stdout}{bypass.stderr}")

        waiting = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "run", "--wait", "30", "--", "true"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        time.sleep(1.0)
        check("a wait does not finish while the lock is held", waiting.poll() is None)

        # SIGKILL, not SIGTERM: the whole claim of this file is that a holder which dies
        # WITHOUT running any cleanup leaves nothing behind. A graceful stop would prove
        # `release` works and prove nothing about the stale-lock case.
        holder.kill()
        holder.wait(timeout=10)
        try:
            out, _ = waiting.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            waiting.kill()
            out = "(timed out)"
        check("the wait acquires once the holder is gone", waiting.returncode == 0, out)
        check("the wait announced itself before waiting", "waiting for" in out, out)

        after = _selftest_run(tmp, ["status"])
        check("a killed holder leaves the lock free", "free" in after.stdout, after.stdout)

        passthrough = _selftest_run(tmp, ["run", "--", "sh", "-c", "exit 3"])
        check("the command's exit code survives", passthrough.returncode == 3,
              f"exit {passthrough.returncode}")
        check("a finished run leaves no record", held.stat().st_size == 0,
              held.read_text(encoding='utf-8', errors='replace'))

        usage = _selftest_run(tmp, ["run", "--"])
        check("a run with no command is a usage error", usage.returncode == 2, usage.stderr)
    finally:
        if holder is not None and holder.poll() is None:
            holder.kill()
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print(f"suite-lock selftest: {len(failures)} FAILED")
        return 1
    print("suite-lock selftest: ok")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="One browser fleet at a time on this machine.")
    sub = parser.add_subparsers(dest="verb")

    run = sub.add_parser("run", help="take the lock, run the command, release it")
    run.add_argument("--name", default=DEFAULT_NAME)
    run.add_argument("--wait", nargs="?", type=int, const=DEFAULT_WAIT_SECONDS, default=None,
                     metavar="SECONDS",
                     help="queue behind the holder instead of refusing")
    run.add_argument("command", nargs=argparse.REMAINDER)
    run.set_defaults(func=do_run)

    status = sub.add_parser("status", help="who holds it")
    status.add_argument("--name", default=DEFAULT_NAME)
    status.set_defaults(func=do_status)

    selftest = sub.add_parser("selftest", help="the guard, against a throwaway lock directory")
    selftest.set_defaults(func=do_selftest)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    if getattr(args, "command", None) and args.command and args.command[0] == "--":
        args.command = args.command[1:]
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
