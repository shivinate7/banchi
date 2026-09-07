#!/usr/bin/env python3
"""One supervisor, two children, one bookmark.

`make server` and `make dev` are two blocking terminals and a discipline nobody can keep.
The discipline is the expensive half: `docs/GATES.md` records `store/master.py:now()` moving
to milliseconds at 20:16 while box 95's 22:08 run still wrote whole-second stamps, because
the server process predated the fix — "a long-running `make server` outlives the fix that was
written for it." That file files it as a restart discipline. This file is the machinery that
replaces it, which is the move D42 already made when a rule nobody had written let main move
under three live worktrees twice in one day.

WHAT THIS IS NOT: a process manager with opinions. It starts two children, keeps them alive,
watches the Python trees the capture server imports, and restarts that child when they move.
`make server` and `make dev` still work exactly as they did — this is additive, and a session
that wants a foreground server with its own terminal should still use them.

STDLIB ONLY, and the reason is the Makefile's, not a preference: its header states that the
capture server must never NEED `make venv`, because every route it serves is stdlib. A
supervisor that imported `watchdog` to watch files would make that false by the back door. It
may import `store.files` and `server.ports` — both are stdlib at module scope — and may never
import `capture_server`, which pulls in the whole server.

FSEvents was the other option and buys nothing here: it coalesces and delivers directory-level
events with its own latency, so the debounce below would still be needed, and an `os.walk` plus
`stat` over six trees costs under a millisecond once a second.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, List, NamedTuple, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

# `server/ports.py` is the single derivation of both ports (D43) and `store/files.py` owns the
# lock timeout the drain grace is computed from. Importing them rather than restating either is
# the whole point: a second spelling of a port is the defect D43 exists to close, and a second
# spelling of 30 seconds would silently turn a legitimate `store_busy` into a dead socket.
sys.path.insert(0, str(REPO_ROOT))
import envfile  # noqa: E402
from server import ports  # noqa: E402
from store import files as store_files  # noqa: E402

# The name the owner's own DNS answers with — `pkmnscan.lan` on their UniFi. Documented in
# docs/specs/capture-server.md beside the allowlist variable it feeds.
LAN_NAME_ENV = "PKMNSCAN_LAN_NAME"

# ---------------------------------------------------------------------------- state on disk

# `.serve` and deliberately not `.run`, which would sit beside `runs/` — `cli/runs.py`'s
# namespace, and a distinction nobody holds in their head at a grep. Inside the checkout so it
# is per-checkout for free and dies with a deleted worktree.
STATE_DIRNAME = ".serve"

SUPERVISOR_PID = "supervisor.pid"
SUPERVISOR_LOG = "supervisor.log"
CAPTURE_PID = "capture.pid"
CAPTURE_LOG = "capture.log"
VITE_PID = "vite.pid"
VITE_LOG = "vite.log"

# launchd appends to StandardOutPath forever, so a Mac left on for a month grows a few hundred
# megabytes in a directory nobody looks at. Rotated at startup rather than on every write: the
# check is one `stat` and the failure it prevents is slow.
LOG_MAX_BYTES = 5 * 1024 * 1024

# ---------------------------------------------------------------------------- timing

POLL_SECONDS = 1.0

# The fingerprint must be unchanged this long before a restart. An editor writing a file is
# several syscalls, and a formatter-on-save is a second write a beat later; restarting between
# them would restart on half a change and then again on the rest.
QUIET_SECONDS = 0.75

# DERIVED, NEVER CHOSEN. `store/files.py:LOCK_TIMEOUT_SECONDS` is 30, and a capture posted
# while `./pkmnscan identify` holds the store lock legitimately takes that long before it
# answers `store_busy`. A shorter grace would convert a true refusal into a killed request —
# the same argument `app/src/server.ts` makes one process over for having no client timeout
# below 30s.
DRAIN_GRACE_SECONDS = store_files.LOCK_TIMEOUT_SECONDS + 10

# How long a fresh child gets to bind before we say so. Not a failure if it overruns — the
# crash path below covers a child that dies — but silence while a page will not load is worse
# than a line saying what is being waited for.
READY_SECONDS = 10.0

RESTART_BACKOFF = (1, 2, 4, 8, 15, 30)

# After this many fast failures, stop respawning and KEEP WATCHING. See `_note_exit`.
FAST_FAILURE_LIMIT = 5
FAST_FAILURE_SECONDS = 5.0

# ---------------------------------------------------------------------------- the watch set

# Every tree the capture server imports at runtime. `envfile.py` is here because
# `identify/batch.py` imports it and identify runs inside this process; `harness/` is not,
# because nothing the server serves imports it.
WATCH_DIRS = (
    "server",
    "store",
    "pipeline",
    "cli",
    "identify",
    "geometry",
    # THE CODE-CARD TRACK, ADDED 2026-08-30 WITH D70, AND ITS ABSENCE WAS CAUGHT THE ONLY
    # WAY AN ABSENCE FROM THIS TUPLE EVER IS — by an edit that did nothing. `codes/` landed
    # as a new package, `server/codes_routes.py` imports it, and a fix to
    # `codes/products.py` was invisible to the running server while the screen kept drawing
    # the old answer and looking exactly like a client bug. A tree the capture server
    # imports and this tuple does not name is a tree whose edits silently do not take.
    "codes",
)
WATCH_FILES = ("envfile.py", "scripts/serve.py")

# THE FILES THIS SUPERVISOR IS ITSELF MADE OF, and a change to any of them means the running
# process is stale no matter how many times it restarts its children.
#
# THE SILENT CASE IS THE ONE THAT MATTERS. `server/ports.py` and `store/files.py` are already
# watched, so editing one restarts the CAPTURE CHILD — visibly, in the log, looking exactly
# like the fix landing. But Python caches an imported module, so the supervisor goes on using
# the code it loaded at boot: the child restarts and the parent stays wrong. That reads as
# working, which is worse than not restarting at all.
#
# `scripts/serve.py` is the loud case and the one the owner asked about: nothing watched it,
# so a `git pull` that changed this file left the old image running with no signal at all.
#
# The Makefile is deliberately NOT here. Three comments in this file mention it and nothing
# reads it — `make` re-reads it from disk on every invocation, so it cannot make a running
# process stale. That was claimed once in conversation and is wrong.
SELF_FILES = (
    "scripts/serve.py",
    "envfile.py",
    "server/ports.py",
    "store/files.py",
)
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv"}


class Fingerprint(dict):
    """`{path: (mtime_ns, size)}`.

    A dict rather than a digest so a restart can NAME the file that caused it. That is the only
    thing that connects a restart the operator did not ask for to the save they just made, and
    a hash cannot say it.
    """


def fingerprint(root: Path = REPO_ROOT) -> Fingerprint:
    seen = Fingerprint()
    for name in WATCH_DIRS:
        base = root / name
        if not base.is_dir():
            continue
        # followlinks=False: a worktree provisions symlinks (D47), and walking through one
        # would fingerprint another tree's files and restart this tree's server for them.
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                path = Path(dirpath) / filename
                try:
                    stat = path.stat()
                except OSError:
                    # Vanished between walk and stat. Not an error: the next pass sees the
                    # truth, and a watcher that raises on a deleted file is a watcher that dies
                    # the first time someone runs `git checkout`.
                    continue
                seen[str(path)] = (stat.st_mtime_ns, stat.st_size)
    for name in set(WATCH_FILES) | set(SELF_FILES):
        path = root / name
        try:
            stat = path.stat()
        except OSError:
            continue
        seen[str(path)] = (stat.st_mtime_ns, stat.st_size)
    return seen


def changed_between(old: Fingerprint, new: Fingerprint) -> list[str]:
    names = set(old) | set(new)
    return sorted(name for name in names if old.get(name) != new.get(name))


# ---------------------------------------------------------------------------- pidfiles

class Child(NamedTuple):
    label: str
    pidfile: str
    logfile: str


CAPTURE = Child("capture", CAPTURE_PID, CAPTURE_LOG)
VITE = Child("app", VITE_PID, VITE_LOG)


def state_dir(root: Path = REPO_ROOT) -> Path:
    return root / STATE_DIRNAME


def _pid_path(child: Child, root: Path = REPO_ROOT) -> Path:
    return state_dir(root) / child.pidfile


def write_pidfile(child: Child, pid: int, argv: list[str], root: Path = REPO_ROOT) -> None:
    """The pid AND the argv it belongs to.

    `server/pipeline_routes.py:_live_pid` is the house pattern and it only ever READS — a
    recycled pid makes it wrongly report a run as busy, which is annoying. `down` SIGNALS, and
    `os.killpg` on a recycled pid kills an unrelated process tree on the owner's Mac. So the
    marker carries enough to prove the pid is still the process we started.
    """
    payload = {"pid": pid, "argv": argv, "started_at": time.time()}
    path = _pid_path(child, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def read_pidfile(child: Child, root: Path = REPO_ROOT) -> Optional[dict]:
    try:
        return json.loads(_pid_path(child, root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def clear_pidfile(child: Child, root: Path = REPO_ROOT) -> None:
    with contextlib.suppress(OSError):
        _pid_path(child, root).unlink()


def _command_of(pid: int) -> str:
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip()


def _needle(argv: List[str]) -> str:
    """The one argument that says WHICH TREE this child belongs to.

    THE LAST ABSOLUTE PATH, NOT THE LAST ARGUMENT, AND VITE IS WHY. This was `argv[-1]` until
    2026-09-06, which is right for the two children whose last argument IS the path — the
    supervisor's `/abs/scripts/serve.py` and capture's `/abs/server/capture_server.py` — and
    degenerate for the third. Vite's argv is

        ["npm", "--prefix", "/abs/app", "run", "dev"]

    so the needle was `"dev"`, a substring of essentially every `npm run dev` on the machine,
    in any tree. That is exactly the basename check `live_pid` spends a paragraph forbidding,
    and `_sweep_orphans` signals a process group on the strength of it: a recycled pid landing
    on any Vite anywhere would have been swept as ours. Found by reading, not by an incident —
    there is live material for it, an `npm run dev --prefix app` the Browser pane starts from
    `.claude/launch.json` in a tree that has no `.serve/` pidfiles at all.

    Searching from the END keeps the two that were already right: the interpreter is absolute
    too, and it is the argument a path check would otherwise find first.
    """
    for item in reversed(argv):
        if item.startswith("/"):
            return item
    return argv[-1] if len(argv) > 1 else argv[0]


def live_pid(child: Child, root: Path = REPO_ROOT) -> Optional[int]:
    """The pid if it is alive AND is still the process we recorded, else None.

    Two gates, and the second is the one that matters. `os.kill(pid, 0)` proves something is
    running; it does not prove it is ours. A Mac that slept through a run leaves a pid that
    belongs to nobody — and, eventually, to somebody else.
    """
    record = read_pidfile(child, root)
    if not record:
        return None
    pid = record.get("pid")
    if not isinstance(pid, int):
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    argv = record.get("argv") or []
    if argv:
        command = _command_of(pid)
        if not command:
            # `ps` said nothing about a pid `os.kill(pid, 0)` accepted. Refuse rather than
            # assume: the caller may be about to signal a process group.
            return None
        # THE FULL PATH, NEVER THE BASENAME, AND THIS REPO IS THE REASON. Every checkout runs
        # a file called `capture_server.py` and an `npm run dev` under a directory called
        # `app`, so a basename check answers "yes, that's ours" for ANOTHER TREE'S SERVER —
        # and `_sweep_orphans` signals a process group on the strength of it. A recycled pid
        # would then take down the main checkout's real server from a worktree, which is D43's
        # cross-tree failure with a kill instead of a write.
        #
        # `ps -o command=` prints the full argv, so the absolute path really is there to match.
        # A worktree's path contains the main tree's as a prefix, so the match has to be on the
        # distinguishing argument rather than on the root.
        needle = _needle(argv)
        if needle not in command:
            return None
    return pid


def supervisor_pid(root: Path = REPO_ROOT) -> Optional[int]:
    return live_pid(Child("supervisor", SUPERVISOR_PID, SUPERVISOR_LOG), root)


# ---------------------------------------------------------------------------- logging

def _rotate(path: Path) -> None:
    try:
        if path.exists() and path.stat().st_size > LOG_MAX_BYTES:
            path.replace(path.with_suffix(path.suffix + ".1"))
    except OSError:
        pass


def log(message: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


# ---------------------------------------------------------------------------- spawning

def python_executable(root: Path = REPO_ROOT) -> str:
    """The Makefile's own rule, resolved AT SPAWN rather than baked.

    That timing is what lets the LaunchAgent name the system `python3` for the supervisor while
    `POST /pipeline/crop-preview` still gets Pillow out of the venv — and it means a rebuilt
    venv is picked up on the next restart with no plist to regenerate.
    """
    candidate = root / ".venv" / "bin" / "python"
    return str(candidate) if os.access(candidate, os.X_OK) else "python3"


def _origins_env_name(root: Path = REPO_ROOT) -> str:
    """`ORIGINS_ENV` lifted out of the capture server WITHOUT importing it.

    Two rules meet here. This file may not import `capture_server` — the supervisor would then
    hold a copy of the code it supervises, and would itself need restarting to pick up a change
    it exists to apply to something else. And a second hand-written spelling of an environment
    variable is the drift `docs/DECISIONS.md` D16 is about: the two would agree until the day
    one moved, and the symptom would be writes silently 403ing from the LAN.

    So it is read with `ast`, which is this repo's own answer to exactly this — the docs audit
    parses rather than imports for the same reason, and runs no project code doing it. The
    literal below is a fallback for an unreadable tree, not a second source of truth: if the
    parse fails the name is still right today, and the failure it protects against is the file
    being absent rather than the constant being renamed.
    """
    import ast

    try:
        tree = ast.parse((root / "server" / "capture_server.py").read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return "PKMNSCAN_ALLOWED_ORIGINS"
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "ORIGINS_ENV"
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    return node.value.value
    return "PKMNSCAN_ALLOWED_ORIGINS"


ORIGINS_ENV = _origins_env_name()


def lan_hostnames() -> list[str]:
    """The names this Mac answers to on the network, for the origin allowlist.

    Bonjour publishes `<LocalHostName>.local`, and the owner's UniFi maps a chosen name at a
    reserved address. Both are collected because they are different paths to the same machine
    and either may be the one in the address bar.
    """
    names: list[str] = []
    try:
        out = subprocess.run(
            ["scutil", "--get", "LocalHostName"],
            capture_output=True, text=True, timeout=5,
        )
        local = out.stdout.strip()
        if local:
            names.append(f"{local}.local")
    except (OSError, subprocess.SubprocessError):
        pass
    # THE OWNER'S CHOSEN NAME, FROM `.env` RATHER THAN A SHELL PROFILE. D47's amendment
    # settled that: an export in `~/.zshenv` fixes an interactive shell and does nothing for a
    # process launchd starts, which reads no profile at all — and `.env` is what every reader
    # of this repo already consults regardless of shell. `envfile.get` still lets a real
    # environment variable win.
    extra = envfile.get(LAN_NAME_ENV) or os.environ.get(LAN_NAME_ENV, "")
    for name in extra.replace(",", " ").split():
        if name:
            names.append(name)
    return names


def _child_env(root: Path = REPO_ROOT) -> dict:
    """The capture server's environment, with the LAN origins added.

    THE ALLOWLIST IS SET HERE RATHER THAN EDITED IN THE SERVER, and that is the whole of the
    LAN change on this side. `PKMNSCAN_ALLOWED_ORIGINS` already exists, is already documented,
    is read fresh on every request, and EXTENDS the two defaults rather than replacing them —
    so a name added here can never turn the gate off. `*` is not a wildcard in that reader; it
    is compared as an exact string and therefore refuses everything, which T7 asserts.
    Composing the value is all this needs to do.
    """
    env = dict(os.environ)
    dev = ports.dev_port(root)
    names = lan_hostnames()
    if not names:
        return env
    origins = [f"http://{name}:{dev}" for name in names]
    # EXTEND whatever the operator already set rather than replacing it — the same rule the
    # variable itself follows one process over. Somebody who exported their own origin for a
    # reason should not lose it by starting the server a different way.
    existing = env.get(ORIGINS_ENV, "").strip()
    if existing:
        origins = [existing] + origins
    env[ORIGINS_ENV] = " ".join(origins)
    return env


def spawn_capture(root: Path = REPO_ROOT) -> Optional[subprocess.Popen]:
    argv = [python_executable(root), str(root / "server" / "capture_server.py")]
    logfile = state_dir(root) / CAPTURE_LOG
    logfile.parent.mkdir(parents=True, exist_ok=True)
    _rotate(logfile)
    handle = open(logfile, "a", buffering=1)  # noqa: SIM115 — outlives this function as the detached child's stdout
    try:
        # start_new_session so the child leads its own process group. Not a detail: `killpg` is
        # the only way to take down a tree, and without it a `kill` reaches the parent alone.
        child = subprocess.Popen(
            argv, cwd=str(root), env=_child_env(root),
            stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as exc:
        log(f"could not start the capture server: {exc}")
        return None
    write_pidfile(CAPTURE, child.pid, argv, root)
    return child


def spawn_vite(root: Path = REPO_ROOT) -> Optional[subprocess.Popen]:
    if not (root / "app" / "node_modules").is_dir():
        # Deliberately not an install. The Makefile's NPM_GUARD argument stands: an implicit
        # 80 MB network fetch hidden inside a command that says "serve" is a surprise, and the
        # capture server is useful without the app.
        log("app/node_modules is missing — not starting the app.")
        log("  fix: npm --prefix app install")
        return None
    argv = ["npm", "--prefix", str(root / "app"), "run", "dev"]
    logfile = state_dir(root) / VITE_LOG
    logfile.parent.mkdir(parents=True, exist_ok=True)
    _rotate(logfile)
    handle = open(logfile, "a", buffering=1)  # noqa: SIM115 — outlives this function as the detached child's stdout
    try:
        child = subprocess.Popen(
            argv, cwd=str(root), env=_child_env(root),
            stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as exc:
        log(f"could not start the app: {exc}")
        log("  is npm on PATH? under launchd it often is not — see `make launch-agent`.")
        return None
    write_pidfile(VITE, child.pid, argv, root)
    return child


def stop_child(child: subprocess.Popen, grace: float, label: str) -> bool:
    """SIGTERM the group, wait, SIGKILL. True if it went down gracefully.

    `npm run dev` is npm wrapping node, so signalling the child alone orphans a node process
    still holding the dev port — where `strictPort: true` turns that into a failed start rather
    than a silent move to 5174. The group is the unit.
    """
    try:
        pgid = os.getpgid(child.pid)
    except OSError:
        return True
    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        return True
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        if child.poll() is not None:
            return True
        time.sleep(0.05)
    log(f"{label} did not stop within {grace:.0f}s — killing it.")
    log("  a request in flight was cut. If the store looks wrong, check history.jsonl.")
    with contextlib.suppress(OSError):
        os.killpg(pgid, signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired):
        child.wait(timeout=5)
    return False


def port_answering(port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def port_holder(port: int) -> Optional[Tuple[int, str]]:
    """The pid and command line of whatever is listening, or None.

    Asked only when something has ALREADY gone wrong, so the cost of shelling out to `lsof`
    is paid once on a path that is about to print a paragraph anyway. It exists because
    "port is busy" is not an actionable sentence: the operator needs to know whether the
    holder is their own supervisor, a stray foreground server, or another checkout — and
    those three have three different remedies.
    """
    try:
        out = subprocess.run(
            ["lsof", "-nP", "-tiTCP:%d" % port, "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    first = out.stdout.split()
    if not first:
        return None
    try:
        pid = int(first[0])
    except ValueError:
        return None
    return pid, _command_of(pid)


def short_command(command: str, width: int = 108) -> str:
    """The TAIL of a command line, not the head.

    `ps` prints the interpreter first, and on this machine that is a 96-character path into
    CommandLineTools before the script name is even reached — so a head-truncated line
    identified the process as "Python" and nothing else, on the one screen whose entire job is
    telling you WHICH process to go and kill. The distinguishing part of every command this
    supervisor deals with is at the end.
    """
    command = command.strip()
    if len(command) <= width:
        return command
    return "…" + command[-(width - 1):]


def wait_for_port(port: int, timeout: float,
                  child: Optional[subprocess.Popen] = None) -> float:
    """Wait for the port to answer — and, given a child, that OUR child is what answers.

    THE CHILD ARGUMENT IS THE WHOLE POINT, AND ITS ABSENCE WAS A REAL DEFECT. This probed the
    socket alone, so a port held by somebody else satisfied it: a stray `make server` on :8000
    answered, `make up` reported "pkmnscan is up", and the capture child it had just spawned
    was in a retry loop that would never succeed. Observed on the owner's machine — the app
    served fine off the squatter and silently stopped reloading on edit, which is the exact
    failure the supervisor exists to prevent.

    A liveness probe another process can satisfy is not a liveness probe.
    """
    started = time.monotonic()
    deadline = started + timeout
    while time.monotonic() < deadline:
        if child is not None and child.poll() is not None:
            # Our child is gone. Anything answering now belongs to someone else, and reporting
            # success on it is how the half-started stack got called started.
            return -1.0
        if port_answering(port):
            return time.monotonic() - started
        time.sleep(0.1)
    return -1.0


# ---------------------------------------------------------------------------- report

def report(root: Path = REPO_ROOT) -> dict:
    """Read-only. `scripts/status.py` calls this and nothing else.

    Opens no file for writing, signals nothing, starts nothing. `make status` is the one
    surface whose whole job is saying what state you are actually in, and a status command
    with a side effect is a status command nobody can trust.
    """
    capture_port = ports.capture_port(root)
    dev_port = ports.dev_port(root)
    sup = supervisor_pid(root)
    capture = live_pid(CAPTURE, root)
    vite = live_pid(VITE, root)
    return {
        "supervisor": sup,
        "capture_pid": capture,
        "capture_port": capture_port,
        "capture_answering": port_answering(capture_port),
        "app_pid": vite,
        "dev_port": dev_port,
        "app_answering": port_answering(dev_port),
        "worktree": ports.is_linked_worktree(root),
        "state_dir": str(state_dir(root)),
        # PRESENCE, LABELLED AS SUCH — not "running under launchd". `launchctl print` is slow
        # and its output is not stable enough to parse in a status tool, and a status line that
        # guesses is worse than one that says less.
        "agent_installed": agent_installed(root),
        "agent_label": ports.agent_label(root),
        "lan_names": lan_hostnames(),
    }


def urls(root: Path = REPO_ROOT) -> tuple[str, str]:
    return (
        f"http://localhost:{ports.dev_port(root)}",
        f"http://localhost:{ports.capture_port(root)}",
    )


def print_where(root: Path = REPO_ROOT) -> None:
    app_url, capture_url = urls(root)
    print("pkmnscan is up.")
    print(f"  app       {app_url}     <- bookmark this")
    print(f"  capture   {capture_url}")
    print(f"  logs      {STATE_DIRNAME}/supervisor.log · {STATE_DIRNAME}/capture.log")
    print("  stop      make down")
    if ports.is_linked_worktree(root):
        # The same sentence `serve()` prints, for the same reason: a worktree's server over a
        # worktree's empty store looks exactly like the real one until a capture lands
        # somewhere that gets deleted with the branch.
        print(f"  WORKTREE  {root.name} — this is NOT the main checkout's store")
        print(f"            main tree serves :{ports.CAPTURE_BASE_PORT}")


# ---------------------------------------------------------------------------- the supervisor

class Supervisor:
    def __init__(self, root: Path = REPO_ROOT, watch: bool = True) -> None:
        self.root = root
        self.watch = watch
        self.capture: Optional[subprocess.Popen] = None
        self.vite: Optional[subprocess.Popen] = None
        self.stopping = False
        self.fingerprint = fingerprint(root) if watch else Fingerprint()
        self.pending: set[str] = set()
        self.quiet_since = 0.0
        self.fast_failures = 0
        self.giving_up = False
        self.restarts = 0
        self.last_syntax_error: Optional[tuple[str, str]] = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Capture first, and the app ONLY if capture came up.

        A HALF-STARTED STACK IS NOT A STARTED STACK, and shipping one is worse than failing.
        This used to start the app unconditionally, so a capture server that could not bind
        left the operator with a working-looking screen served by whatever else held the port
        — reading the right store, and never reloading on an edit. The app alone is not a
        product; the whole reason this supervisor exists is the half that did not start.
        """
        capture_port = ports.capture_port(self.root)
        self.capture = spawn_capture(self.root)
        if self.capture is None:
            return
        took = wait_for_port(capture_port, READY_SECONDS, self.capture)
        if took < 0:
            self._refuse_capture(capture_port)
            return
        log(f"capture server ready on :{capture_port} (pid {self.capture.pid}) in {took:.1f}s")

        self.vite = spawn_vite(self.root)
        if self.vite is not None:
            log(f"app starting on :{ports.dev_port(self.root)} (pid {self.vite.pid})")

    def _refuse_capture(self, capture_port: int) -> None:
        """The capture server did not come up. Say why, and stop — do not retry a wall.

        A PORT SOMEBODY ELSE HOLDS IS NOT A CRASH, and treating it as one is what burned five
        retries and a backoff on a condition that cannot change without a human. `_note_exit`
        below is right for a child that started and died; this is for one that never got to
        start, and the two want opposite behaviour.
        """
        self.giving_up = True
        held = port_holder(capture_port)
        if held is not None and (self.capture is None or held[0] != self.capture.pid):
            pid, command = held
            log(f"NOT STARTING: :{capture_port} is already held by pid {pid}")
            if command:
                log(f"  {short_command(command)}")
            log("  So this supervisor did not start, and neither did the app — a stack that")
            log("  is half up reads as working and does not reload when you edit Python.")
            log("  `make status` says whose it is. `make down` if it is a supervisor;")
            log("  `kill` it if it is a stray `make server`.")
        else:
            log(f"capture server did not answer :{capture_port} within "
                f"{READY_SECONDS:.0f}s — see {STATE_DIRNAME}/{CAPTURE_LOG}")
            self._tail(CAPTURE_LOG)

    def stop(self) -> None:
        self.stopping = True
        if self.vite is not None:
            stop_child(self.vite, 10, "app")
            clear_pidfile(VITE, self.root)
        if self.capture is not None:
            stop_child(self.capture, DRAIN_GRACE_SECONDS, "capture server")
            clear_pidfile(CAPTURE, self.root)
        log("stopped.")

    # -- the loop ----------------------------------------------------------

    def run(self) -> int:
        def _term(_signum, _frame):
            # Always a clean exit. launchd's KeepAlive is {SuccessfulExit: false}, and a
            # process terminated BY A SIGNAL is an unsuccessful exit to launchd — which would
            # restart the very thing `make down` just stopped.
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _term)
        signal.signal(signal.SIGINT, _term)

        write_pidfile(
            Child("supervisor", SUPERVISOR_PID, SUPERVISOR_LOG),
            os.getpid(), [sys.executable, __file__], self.root,
        )
        log(f"supervisor up (pid {os.getpid()}) in {self.root}")
        self.start()
        if self.watch:
            log(f"watching {', '.join(WATCH_DIRS)} for changes")

        try:
            while True:
                time.sleep(POLL_SECONDS)
                self._reap()
                if self.watch:
                    self._check_files()
        except KeyboardInterrupt:
            self.stop()
        return 0

    def _reap(self) -> None:
        """A child that exited without us asking."""
        if self.capture is not None and self.capture.poll() is not None:
            code = self.capture.returncode
            log(f"capture server exited ({code}).")
            self._tail(CAPTURE_LOG)
            clear_pidfile(CAPTURE, self.root)
            self.capture = None
            self._note_exit()
            if not self.giving_up:
                delay = RESTART_BACKOFF[min(self.fast_failures, len(RESTART_BACKOFF) - 1)]
                log(f"restarting in {delay}s")
                time.sleep(delay)
                self.capture = spawn_capture(self.root)
        if self.vite is not None and self.vite.poll() is not None:
            log(f"app exited ({self.vite.returncode}).")
            self._tail(VITE_LOG)
            clear_pidfile(VITE, self.root)
            self.vite = None

    def _note_exit(self) -> None:
        self.fast_failures += 1
        if self.fast_failures >= FAST_FAILURE_LIMIT:
            self.giving_up = True
            log("the capture server has failed to stay up 5 times — not retrying.")
            log("  the supervisor is STILL RUNNING and still watching. Fix the code and")
            log("  save any watched file to try again.")

    def _tail(self, name: str, lines: int = 20) -> None:
        path = state_dir(self.root) / name
        try:
            text = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return
        for line in text[-lines:]:
            log(f"  | {line}")

    # -- the watcher -------------------------------------------------------

    def _check_files(self) -> None:
        current = fingerprint(self.root)
        if current != self.fingerprint:
            self.pending.update(changed_between(self.fingerprint, current))
            self.fingerprint = current
            self.quiet_since = time.monotonic()
            return
        if self.pending and time.monotonic() - self.quiet_since >= QUIET_SECONDS:
            changed = sorted(self.pending)
            self.pending.clear()
            self._restart_for(changed)

    def _touches_self(self, changed: list[str]) -> list[str]:
        """Which of the changed paths are files this supervisor is made of."""
        mine = {str((self.root / name).resolve()) for name in SELF_FILES}
        return sorted(name for name in changed if str(Path(name).resolve()) in mine)

    def _reexec(self, changed: list[str]) -> None:
        """Replace this process with a fresh one running the new code.

        `os.execv` REPLACES THE IMAGE AND KEEPS THE PID, which is the whole reason to use it
        rather than spawning and exiting: `supervisor.pid` stays valid, and launchd sees the
        same process it started rather than an unexpected exit it would try to restart.

        CHILDREN ARE STOPPED FIRST, because exec throws away every Popen handle — anything
        still running would be orphaned, holding the ports the new image is about to want, and
        unreachable from the pidfiles it will write. The drain applies as it always does.
        """
        shown = ", ".join(Path(c).name for c in changed)
        log(f"restarting MYSELF: {shown} changed — the supervisor is made of that file")
        self.stop()
        argv = [python_executable(self.root), str(Path(__file__).resolve()), "run"]
        if not self.watch:
            argv.append("--no-watch")
        try:
            os.execv(argv[0], argv)
        except OSError as exc:
            # Exec failed, and the children are already down. Say so and rebuild them rather
            # than leaving a supervisor that supervises nothing.
            log(f"could not restart myself: {exc}")
            log("  running on with the OLD code. `make restart` to pick up the change.")
            self.stopping = False
            self.start()

    def _restart_for(self, changed: list[str]) -> None:
        bad = self._first_syntax_error(changed)
        if bad is not None:
            path, message = bad
            # THE HIGHEST-VALUE BRANCH IN THIS FILE. Auto-restart guarantees the watcher
            # observes half-written code — an editor saves mid-keystroke and a formatter writes
            # again a beat later. Restarting into a SyntaxError would take the server down and
            # leave nothing serving; refusing leaves the last code that parsed running.
            #
            # Its honest limit, which belongs here rather than in a doc: this catches PARSE
            # errors only. An ImportError, a module-scope NameError or a bad constant still
            # kills the new child, and there is no rolling back to the old one. The fast-failure
            # cap in `_note_exit` is the containment for those.
            #
            # SAID ONCE PER DISTINCT ERROR, not once per retry. The retry below re-arms every
            # QUIET_SECONDS, so logging unconditionally wrote the same two lines every second
            # for as long as the file was broken — which buries the restart lines that are the
            # only reason anyone opens this log. Observed before it was fixed.
            if (path, message) != self.last_syntax_error:
                log(f"not restarting — {path} does not parse: {message}")
                log("  the server is still serving the last code that parsed. Save again.")
                self.last_syntax_error = (path, message)
            # Keep them pending so the next quiet window retries without another edit.
            self.pending.update(changed)
            self.quiet_since = time.monotonic()
            return
        self.last_syntax_error = None

        # A file this supervisor IMPORTS takes priority over the child restart: re-execing
        # rebuilds the children anyway, so doing both would restart them twice.
        mine = self._touches_self(changed)
        if mine:
            self._reexec(mine)
            return

        shown = ", ".join(Path(p).relative_to(self.root).as_posix()
                          if Path(p).is_absolute() else p for p in changed[:3])
        more = f" (+{len(changed) - 3} more)" if len(changed) > 3 else ""
        log(f"restarting: {len(changed)} file(s) changed — {shown}{more}")

        if self.capture is not None:
            stop_child(self.capture, DRAIN_GRACE_SECONDS, "capture server")
            clear_pidfile(CAPTURE, self.root)
        self.capture = spawn_capture(self.root)
        self.restarts += 1
        self.fast_failures = 0
        self.giving_up = False
        if self.capture is not None:
            took = wait_for_port(ports.capture_port(self.root), READY_SECONDS, self.capture)
            if took >= 0:
                log(f"capture server ready on :{ports.capture_port(self.root)} "
                    f"(pid {self.capture.pid}) in {took:.1f}s")
            else:
                log("capture server did not come back up:")
                self._tail(CAPTURE_LOG)

    def _first_syntax_error(self, changed: Iterable[str]) -> Optional[tuple[str, str]]:
        for name in changed:
            path = Path(name)
            if path.suffix != ".py" or not path.exists():
                continue
            try:
                source = path.read_bytes()
            except OSError:
                continue
            try:
                compile(source, str(path), "exec")
            except SyntaxError as exc:
                where = f"{path.name}:{exc.lineno}" if exc.lineno else path.name
                return (where, exc.msg or "syntax error")
            except ValueError as exc:
                return (path.name, str(exc))
        return None


# ---------------------------------------------------------------------------- verbs

def do_run(args: argparse.Namespace) -> int:
    logfile = state_dir(REPO_ROOT) / SUPERVISOR_LOG
    logfile.parent.mkdir(parents=True, exist_ok=True)
    _rotate(logfile)
    return Supervisor(REPO_ROOT, watch=not args.no_watch).run()


def do_up(args: argparse.Namespace) -> int:
    existing = supervisor_pid()
    if existing is not None:
        print(f"already running (pid {existing}).")
        print_where()
        return 0
    # PREFLIGHT, BEFORE ANYTHING IS SPAWNED. `supervisor_pid()` above answers "is OUR
    # supervisor up"; it says nothing about the port, and the port is what actually decides
    # whether a capture server can start. Checking here means the refusal costs no processes
    # at all, where discovering it after the spawn left a supervisor and an app running
    # around a capture server that never bound.
    capture_port = ports.capture_port()
    held = port_holder(capture_port)
    if held is not None:
        pid, command = held
        print(f":{capture_port} is already held by pid {pid}")
        if command:
            print(f"  {short_command(command)}")
        print()
        print("  Started nothing. A stack that is half up reads as working and does not")
        print("  reload when you edit Python, so this refuses rather than joining it.")
        print()
        print("  make status   says whose it is")
        print("  make down     if it is a supervisor in this checkout")
        print(f"  kill {pid}       if it is a stray `make server`")
        return 1

    _sweep_orphans()
    state_dir(REPO_ROOT).mkdir(parents=True, exist_ok=True)
    logfile = state_dir(REPO_ROOT) / SUPERVISOR_LOG
    _rotate(logfile)
    handle = open(logfile, "a", buffering=1)  # noqa: SIM115 — outlives this function as the detached child's stdout
    argv = [python_executable(), str(Path(__file__).resolve()), "run"]
    if args.no_watch:
        argv.append("--no-watch")
    subprocess.Popen(
        argv, cwd=str(REPO_ROOT),
        stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    took = wait_for_port(ports.capture_port(), READY_SECONDS)
    if took < 0:
        print(f"the capture server did not answer within {READY_SECONDS:.0f}s.")
        print(f"  see {STATE_DIRNAME}/{SUPERVISOR_LOG} and {STATE_DIRNAME}/{CAPTURE_LOG}")
        return 1
    print_where()
    return 0


def _sweep_orphans(root: Path = REPO_ROOT) -> None:
    """Children of a supervisor that was killed with -9, in `root`'s own `.serve/`.

    This is why there is a pidfile per child rather than one for the supervisor alone: without
    them an orphaned `npm run dev` keeps the dev port, and `strictPort` turns the next start
    into a failure rather than a silent move.

    IT ANSWERS FOR ONE TREE AND CANNOT REACH ANOTHER, WHICH IS THE POINT OF THE ARGUMENT.
    `root` was `REPO_ROOT` and nothing else until 2026-09-06, so `scripts/janitor.py` — which
    is handed a tree — had no way to ask this question without reimplementing it. What it
    still does NOT cover is the supervisor itself, and it never can: a supervisor whose tree
    was deleted has no `.serve/` left to read, because `.serve/` lives inside the tree. That
    case is the janitor's, and it is answered from the process table instead.
    """
    for child in (CAPTURE, VITE):
        pid = live_pid(child, root)
        if pid is None:
            clear_pidfile(child, root)
            continue
        print(f"sweeping orphaned {child.label} (pid {pid})")
        with contextlib.suppress(OSError):
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        clear_pidfile(child, root)


def owned_by_agent(root: Path = REPO_ROOT) -> bool:
    """Is the server on this checkout's port the OWNER'S, kept alive at login?

    Two conditions, and both are needed. A linked worktree's server is its own — its store and
    its ports are per-checkout (D43) — so stopping one costs nobody anything and a refusal there
    would only teach sessions to reach past this guard. The main tree with an agent installed is
    the case where a stop reaches a process somebody else is using.
    """
    return not ports.is_linked_worktree(root) and agent_installed(root)


def refuse_unconfirmed(args: argparse.Namespace, verb: str) -> bool:
    """True when this stop must not proceed. Shaped on `make merge` (D42), deliberately.

    THE COMMAND IS RIGHT AND THE MOMENT IS WRONG, which is the same class D42 built the
    preview/confirm shape for, so this reuses it rather than inventing a second vocabulary for
    it. A bare `make down` in the main tree previews and presses nothing; `--confirm` performs
    it, and the word is still the operator's.

    WHY IT EXISTS. On 2026-09-04 a session ran `make design-check` about eight times against the
    owner's live server, degraded it the way `docs/DEBTS.md` section 11 describes, and then ran
    `make restart` to fix what it had done. The drain expired and the supervisor killed the
    process with a request in flight, which crashed Python out from under the owner mid-use. The
    wedge is survivable; the kill past the drain is what was not. Nothing on this path said a
    word, because nothing on it knew the process was anyone else's.
    """
    if getattr(args, "confirm", False) or not owned_by_agent():
        return False
    print("refusing: this is the main checkout and a launch agent keeps its server alive.")
    print()
    print("  That server is the one the bookmark points at, over the real store, and something")
    print("  may be mid-request against it right now. Stopping it drains for")
    print(f"  {DRAIN_GRACE_SECONDS:.0f}s and then KILLS whatever is still in flight.")
    print()
    print("  If it stopped answering under load, that is section 11 of docs/DEBTS.md and a")
    print("  restart is not the repair — it is how the write gets cut.")
    print()
    print(f"  make {verb} ARGS=--confirm     do it anyway")
    print("  make launch-agent ARGS=--remove  stop it coming back at login")
    return True


def do_down(_args: argparse.Namespace) -> int:
    # THIS SIGNALS THE SUPERVISOR THAT IS RUNNING, WHATEVER STARTED IT, and the special case
    # that used to sit here is deleted rather than repaired.
    #
    # It read: where an agent is installed, launchctl is the one that has to be told, because
    # `bootout` is how you say "and stay down". Both halves were wrong.
    #
    # WRONG ABOUT THE PREMISE. `KeepAlive` is `{SuccessfulExit: false}` and the SIGTERM handler
    # exits 0, so a signalled supervisor is a SUCCESSFUL exit and launchd leaves it alone.
    # Measured: SIGTERM to a launchd-started supervisor left no process, no pid in `launchctl
    # print`, and no listener. Signalling was always safe.
    #
    # WRONG ABOUT WHICH PROCESS. `bootout` acts on the SERVICE, not on whatever is running —
    # so when the live supervisor had been started by `make up` rather than by launchd, bootout
    # applied to nothing and this printed `stopped.` over a supervisor that was still up.
    # `make launch-agent` then bootstrapped a second one, whose capture child could not bind,
    # gave up after five retries, and overwrote `supervisor.pid` with its own pid. Observed on
    # the owner's machine 2026-08-30.
    #
    # That is the SAME defect as the liveness probe one commit earlier — an action reporting
    # success on the strength of something that did not apply to the process in question — and
    # it survived that fix by living in a branch nobody re-read. Deleting the branch is the
    # repair: one path, and it acts on the pid that is actually there.

    if refuse_unconfirmed(_args, "down"):
        return 1

    pid = supervisor_pid()
    if pid is None:
        _sweep_orphans()
        print("not running.")
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        print(f"could not stop the supervisor (pid {pid}): {exc}")
        return 1
    deadline = time.monotonic() + DRAIN_GRACE_SECONDS + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            break
        time.sleep(0.1)
    else:
        print(f"supervisor (pid {pid}) did not stop — killing it.")
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGKILL)
    clear_pidfile(Child("supervisor", SUPERVISOR_PID, SUPERVISOR_LOG))
    _sweep_orphans()
    print("stopped.")
    # Said here rather than left to be discovered tomorrow morning. The service stays loaded
    # with no process, which is harmless — a clean exit does not trip KeepAlive — and RunAtLoad
    # starts it again at the next login.
    if agent_installed():
        print("  the launch agent starts it again at your next login —")
        print("  `make launch-agent ARGS=--remove` to stop that.")
    return 0


def do_restart(args: argparse.Namespace) -> int:
    """Guarded through `do_down`, which is the only stop path — so there is one refusal and not
    two to keep in step. It returns non-zero without stopping anything when it refuses, and this
    must NOT go on to start a second supervisor over the one still running."""
    if do_down(args) != 0:
        return 1
    return do_up(args)


# ---------------------------------------------------------------------------- launch agent

def agent_plist_path(root: Path = REPO_ROOT) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{ports.agent_label(root)}.plist"


def agent_installed(root: Path = REPO_ROOT) -> bool:
    return agent_plist_path(root).is_file()


def do_launch_agent(args: argparse.Namespace) -> int:
    """Start at login, so the bookmark is always live.

    WRITTEN OUTSIDE THE REPO AND GENERATED RATHER THAN TRACKED. A plist names an absolute path
    on one Mac; a tracked one would be D47's failure verbatim — a machine-specific absolute
    path committed and then checked out somewhere it means something else. `~/Library` is
    strictly better than gitignoring it, because there is no file in the tree to commit by
    accident at all. `plistlib.dump` rather than a here-doc, for `make launch-config`'s own
    stated reason: a hand-built plist is one escaping mistake from a file that presents as
    "the app does not start" rather than as a syntax error.
    """
    import plistlib

    root = REPO_ROOT
    plist = agent_plist_path(root)
    label = ports.agent_label(root)

    if args.remove:
        if not plist.exists():
            print(f"no launch agent installed for this checkout ({label}).")
            return 0
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"],
                       capture_output=True)
        plist.unlink()
        print(f"launch agent removed ({label}).")
        print("  the servers keep running until `make down`.")
        return 0

    # MAIN TREE ONLY, AND THE REFUSAL IS THE POINT. A worktree is deleted routinely and its
    # plist is an absolute path that would outlive it — launchd then retries a directory that
    # is not there, forever, with nothing on screen to say so. Every other verb here works in
    # any tree; only login-persistence is refused, because only it survives the tree.
    if ports.is_linked_worktree(root):
        print(f"refusing: {root.name} is a linked worktree.")
        print("  A worktree is deleted routinely and its launch agent would outlive it —")
        print("  launchd would retry a path that is gone. Install this from the main")
        print("  checkout instead. `make up` works here and does not persist.")
        return 1

    state = state_dir(root)
    state.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": label,
        "ProgramArguments": [python_executable(root), str(Path(__file__).resolve()), "run"],
        "WorkingDirectory": str(root),
        "RunAtLoad": True,
        # {SuccessfulExit: false} AND NOT `true`, WHICH IS WHAT LETS `make down` WIN. A process
        # terminated by a signal is an UNSUCCESSFUL exit to launchd, so `KeepAlive: true` would
        # restart the very thing `make down` had just stopped, forever. With this, the SIGTERM
        # handler's clean `sys.exit(0)` is what tells launchd to leave it alone — and a genuine
        # crash still comes back.
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 10,
        "StandardOutPath": str(state / SUPERVISOR_LOG),
        "StandardErrorPath": str(state / SUPERVISOR_LOG),
        # THE CLASSIC FAILURE OF THIS EXACT PLIST. launchd gives an agent a minimal PATH that
        # does not include Homebrew or nvm, so `npm` is simply not found and the app half never
        # starts while the capture server looks fine. Baking the generating shell's PATH is the
        # fix; its limit is honest and named in the decision entry — if npm comes from nvm, a
        # `nvm install` moves it and this needs regenerating.
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    }
    plist.parent.mkdir(parents=True, exist_ok=True)
    with open(plist, "wb") as handle:
        plistlib.dump(payload, handle)

    # bootstrap/bootout/kickstart rather than the deprecated `load -w`.
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], capture_output=True)
    result = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"wrote {plist}")
        print(f"  but launchctl bootstrap failed: {result.stderr.strip() or result.returncode}")
        print("  it will still load at your next login.")
        return 1
    print(f"launch agent installed ({label}).")
    print(f"  plist     {plist}")
    print("  starts at login, and restarts on a crash.")
    print("  remove    make launch-agent ARGS=--remove")
    return 0


FOREGROUND_ENV = "PKMNSCAN_FOREGROUND"


def do_guard_foreground(_args: argparse.Namespace) -> int:
    """`make dev` and `make server` refuse while this checkout's supervisor is up.

    THIS IS WHERE THE SQUATTER COMES FROM. Both ways of starting a server are legitimate and
    neither knew about the other, so a foreground `make server` would take :8000 and the
    supervisor's own capture child could then never bind — leaving the app served by a process
    that watches no files. The collision itself stays loud and deliberate (D43: a server that
    quietly moved would serve a DIFFERENT store); what this removes is the ability to create it
    by accident.

    `PKMNSCAN_FOREGROUND=ok` bypasses, in the shape `PKMNSCAN_MAIN=off` already uses — a guard
    with no visible way past it gets disarmed somewhere worse.
    """
    if os.environ.get(FOREGROUND_ENV, "").strip().lower() in ("ok", "1", "yes"):
        return 0
    pid = supervisor_pid()
    if pid is None:
        return 0
    app_url, capture_url = urls()
    print(f"a supervisor is already running in this checkout (pid {pid}).")
    print(f"  app       {app_url}")
    print(f"  capture   {capture_url}")
    print()
    print("  Starting a foreground server now would take the port its capture child needs,")
    print("  and you would be left with an app that does not reload when you edit Python.")
    print()
    print("  make restart          bounce the supervisor instead")
    print("  make down             stop it, then run this again")
    print(f"  {FOREGROUND_ENV}=ok make …   run anyway")
    return 1


def do_report(args: argparse.Namespace) -> int:
    data = report()
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    for key, value in data.items():
        print(f"{key:20} {value}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the pkmnscan servers.")
    sub = parser.add_subparsers(dest="verb")

    run = sub.add_parser("run", help="foreground; what the LaunchAgent execs")
    run.add_argument("--no-watch", action="store_true", help="do not restart on file changes")
    run.set_defaults(func=do_run)

    up = sub.add_parser("up", help="start detached")
    up.add_argument("--no-watch", action="store_true")
    up.set_defaults(func=do_up)

    down = sub.add_parser("down", help="stop")
    down.add_argument("--confirm", action="store_true",
                      help="stop the main tree's agent-kept server anyway")
    down.set_defaults(func=do_down)

    restart = sub.add_parser("restart", help="stop then start")
    restart.add_argument("--no-watch", action="store_true")
    restart.add_argument("--confirm", action="store_true",
                         help="bounce the main tree's agent-kept server anyway")
    restart.set_defaults(func=do_restart)

    rep = sub.add_parser("report", help="read-only state, for `make status`")
    rep.add_argument("--json", action="store_true")
    rep.set_defaults(func=do_report)

    guard = sub.add_parser("guard-foreground",
                           help="refuse a foreground server while the supervisor is up")
    guard.set_defaults(func=do_guard_foreground)

    agent = sub.add_parser("launch-agent", help="start at login (main tree only)")
    agent.add_argument("--remove", action="store_true")
    agent.set_defaults(func=do_launch_agent)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
