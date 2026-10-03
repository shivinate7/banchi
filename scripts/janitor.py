#!/usr/bin/env python3
"""Stop what a leaving session started in one worktree: its supervisor, via `serve.py down`
(D138, the supervisor's job). The machine-wide sweep is claude-settings' (claude-settings
decisions/the-janitor-is-one-machine-wide-sweep.md, "The janitor is one machine-wide sweep");
`make janitor` runs it.

THE SAFETY RULE (provably dead or reported): a thing is stopped only when nothing can be
live in it. Liveness is read from `~/.claude/sessions/<pid>.json`, never from mtimes. See
`_same_process` for why an unreadable case resolves to LIVE.

    scripts/janitor.py --teardown TREE     stop that tree's servers. What the hook runs.
    scripts/janitor.py --sessions DIR      read the liveness oracle elsewhere, for the self-test.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, NamedTuple, Optional, Sequence, Set, Tuple

SESSIONS_DIR = Path.home() / ".claude" / "sessions"


# Every absolute path in a command line. `ps -o command=` prints the argv space-joined, so a
# path containing a space cannot be recovered — which is why a miss is silent rather than a
# mis-parse, and why nothing here reaps on the strength of a path it could not resolve.
_ABS_PATH_RE = re.compile(r"(/[^\s]+)")



class Ran(NamedTuple):
    ok: bool
    out: str
    err: str


def run(args: Sequence[str], cwd: Optional[str] = None) -> Ran:
    """A subprocess, never a shell. Failure is a value here, not an exception."""
    try:
        done = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, check=False)
    except OSError as exc:
        return Ran(False, "", str(exc))
    return Ran(done.returncode == 0, done.stdout.strip(), done.stderr.strip())


def _real(path: str) -> str:
    """A path in the one spelling every comparison in this file uses.

    EVERY PATH THAT ENTERS FROM OUTSIDE GOES THROUGH HERE, AND A SYMLINK IS WHY. On this
    machine `/tmp` is `/private/tmp` and `/var` is `/private/var`, so `git worktree list`
    answers with the resolved spelling while a session record and a caller's argument
    carry whatever the caller typed. Comparing the two as strings said "no session in this
    tree" for every tree in a temp fixture — the self-test caught it, and the same trap is
    live wherever a checkout sits under a symlinked parent. `server/ports.py:slot_for`
    resolves for exactly this reason and says so.
    """
    try:
        return os.path.realpath(path)
    except OSError:
        return path


def _pid_alive(pid: int) -> bool:
    """Is this pid running right now? ANYTHING THAT IS NOT A DEFINITE "no" READS AS ALIVE.

    It is `os.kill(pid, 0)` and not `ps -o pid= -p`, though the two ask the same question, and
    the reason is the direction-of-safety rule this whole file turns on. `ps` answers with an
    EXIT CODE and an empty line for a pid that is gone — and with exactly the same pair when
    `ps` itself cannot be run at all, so the one case that must read LIVE is indistinguishable
    from the one case that must read DEAD. `os.kill` cannot fail to start, and it separates the
    two by errno: `ProcessLookupError` is the only answer that means gone. `EPERM` means the
    process EXISTS and belongs to somebody else, which `live_sessions` read as dead until this
    function was written.
    """
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def say(*lines: str) -> None:
    for line in lines:
        print(line)






# ------------------------------------------------------------------ the liveness oracle

class Session(NamedTuple):
    pid: int
    cwd: str
    name: str


def _proc_start(pid: int) -> Optional[float]:
    """When the OS says this pid started, in epoch seconds, or None if it cannot be read."""
    got = run(["ps", "-o", "lstart=", "-p", str(pid)])
    if not got.ok or not got.out.strip():
        return None
    try:
        return time.mktime(time.strptime(got.out.strip()))
    except (ValueError, OverflowError):
        return None


def _same_process(record: dict, pid: int) -> bool:
    """Is the pid in this record still the process the record was written about?

    IT COMPARES EPOCHS, AND IT FAILS TOWARD LIVE. Both halves of that were learned the hard
    way on 2026-09-06. The record also carries a `procStart` string, and comparing THAT to
    `ps -o lstart=` looks right and is wrong: the record renders UTC and `ps` renders local, so
    on this machine every pair differed by exactly five hours with identical seconds. Every
    session was therefore judged dead, the oracle returned nought, and the sweep offered to
    reap two trees that had sessions in them — including, had it been clean, the tree the sweep
    was running in.

    `startedAt` is epoch milliseconds and carries no timezone to get wrong; it agrees with
    `ps` to under a second. The tolerance is wide because the record is written just after the
    process starts, not at the same instant.

    THE DIRECTION IS THE SAFETY PROPERTY. A false "live" keeps a tree that could have been
    reaped, and somebody runs the sweep again tomorrow. A false "dead" deletes a tree somebody
    is working in. So anything unreadable — no `startedAt`, an unparseable `ps` — is live.
    """
    started = record.get("startedAt")
    if not isinstance(started, (int, float)):
        return True
    actual = _proc_start(pid)
    if actual is None:
        return True
    return abs(actual - started / 1000.0) <= 120.0


class Oracle(NamedTuple):
    """What the liveness records said, AND WHICH OF THEM WOULD NOT PARSE.

    The second half is not bookkeeping. A record that cannot be read is a session that cannot
    be SEEN, and an unseen session is a tree this sweep would call empty — the same shape of
    failure as the 2026-09-06 timezone bug, arriving by a different door. The old build
    `continue`d past an unparseable file in silence, so the one signal that the oracle was
    incomplete was thrown away at the moment it was produced.
    """
    sessions: List[Session]
    unreadable: List[str]


def live_sessions(sessions_dir: Path) -> Oracle:
    """Every Claude session running right now, and the tree each one is standing in.

    THIS IS THE ONE FACT THAT CANNOT BE INFERRED FROM THE REPOSITORY. A worktree with no dirty
    files, no recent writes and a merged branch is indistinguishable from an abandoned one
    until you ask who is in it, and the answer changes under you: two trees switched branches
    on 2026-09-06 while their supposed idleness was being measured.

    `procStart` is compared as well as the pid, so a pid the OS has since handed to something
    else cannot inherit a dead session's claim on a tree. A record whose pid is gone is simply
    not returned — it is not an error, and it is not worth reporting.
    """
    found = []  # type: List[Session]
    torn = []  # type: List[str]
    if not sessions_dir.is_dir():
        return Oracle(found, torn)
    for path in sorted(sessions_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            torn.append(path.name)
            continue
        pid = record.get("pid")
        cwd = record.get("cwd")
        if not isinstance(pid, int) or not isinstance(cwd, str) or not cwd:
            torn.append(path.name)
            continue
        if not _pid_alive(pid):
            continue
        if not _same_process(record, pid):
            continue
        found.append(Session(pid, _real(cwd), str(record.get("name") or "")))
    return Oracle(found, torn)


def sessions_in(sessions: Sequence[Session], tree: str) -> List[Session]:
    """Sessions standing in `tree` itself or anywhere beneath it."""
    root = Path(_real(tree))
    held = []  # type: List[Session]
    for session in sessions:
        here = Path(session.cwd)
        if here == root or root in here.parents:
            held.append(session)
    return held


# ------------------------------------------------------------------------- the processes

class Server(NamedTuple):
    pid: int
    command: str
    missing: str      # the path in its own argv that no longer exists
    home: str         # the project directory that path belonged to


def _process_table() -> List[Tuple[int, str]]:
    got = run(["ps", "-axww", "-o", "pid=,command="])
    if not got.ok:
        return []
    rows = []  # type: List[Tuple[int, str]]
    for line in got.out.splitlines():
        line = line.strip()
        if not line:
            continue
        head, _, command = line.partition(" ")
        try:
            pid = int(head)
        except ValueError:
            continue
        if command.strip():
            rows.append((pid, command.strip()))
    return rows


def servers_under(tree: str, skip: Set[int],
                  table: Optional[Sequence[Tuple[int, str]]] = None,
                  dirs: Optional[dict] = None) -> List[Server]:
    """Anything running out of `tree` — by a path in its argv, OR by the directory it runs in.

    Reported, never reaped by this sweep: a tree that still exists may have a person in it, and
    stopping a server is `make down`'s job and the teardown hook's. The janitor's interest is
    only in saying that it is there.

    THE SECOND ARM WAS MISSING AND `_placed` HAD IT ALL ALONG. Two functions in this one file
    asked "does this process run out of that tree" and answered differently: `_placed` reads the
    argv AND the working directory, this read the argv alone. So the exact incident `_placed`
    was widened for — `bash scratchpad/autodrive.sh`, whose command line carries no path under
    any checkout — did NOT stop its tree being offered for removal, and removing the tree under
    it is how 2026-09-06's four restarting supervisors were made. One question, one answer.

    `skip` IS A CHAIN AND NOT A PID, AND THE SECOND ARM IS WHY. The old exclusion was
    `pid == mine`, which was enough while only the argv was read: the sweep's own `python3
    scripts/janitor.py` carries no absolute path. A working directory does. Run from a linked
    worktree, the SHELL that started the sweep is standing in that very tree — so the tree
    would report "a server is running out of it" about the sweep asking the question, and a
    genuinely reapable tree could never be offered while anybody swept from inside it.
    The answer is to exclude this process and every ancestor of it.

    `table` and `dirs` are passed in by `sweep` so that every tree and every husk is judged
    against ONE sample of the process table. Read per call, twenty trees meant twenty `ps` runs
    over three seconds, and two trees judged a second apart were judged against two different
    machines.
    """
    root = _real(tree)
    rows = _process_table() if table is None else table
    where = {} if dirs is None else dirs
    found = []  # type: List[Server]
    for pid, command in rows:
        if pid in skip:
            continue
        if _placed(command, where.get(pid, ""), root):
            found.append(Server(pid, command, "", root))
    return found


def _under(path: str, root: str) -> bool:
    """Is `path` `root` itself or inside it? Both are expected to be resolved already."""
    return bool(root) and (path == root or path.startswith(root + os.sep))


def _process_tree() -> dict:
    """{pid: (ppid, command)} in ONE `ps`, because the parent link is what ownership is.

    `_process_table` answers the two older callers, which only ever ask what a command line
    says. This one is separate rather than a widening of it: nothing above needs the parent,
    and a tuple that grew a third field would have to be unpacked in four places to add a
    column three of them ignore.
    """
    got = run(["ps", "-axww", "-o", "pid=,ppid=,command="])
    if not got.ok:
        return {}
    rows = {}  # type: dict
    for line in got.out.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        command = parts[2].strip()
        if command:
            rows[pid] = (ppid, command)
    return rows


def _chain(tree: dict, start: int) -> List[int]:
    """`start` and every ancestor of it, nearest first, stopping short of pid 1.

    The loop is bounded and revisit-guarded because this walks a table that was sampled a
    moment ago and is already out of date: a pid can be gone, and a re-used pid can in
    principle point back into the chain. Neither may hang the sweep.
    """
    walk = []  # type: List[int]
    seen = set()  # type: Set[int]
    cur = start
    for _ in range(64):
        if cur <= 1 or cur in seen:
            break
        seen.add(cur)
        walk.append(cur)
        row = tree.get(cur)
        if row is None:
            break
        cur = row[0]
    return walk




def _placed(command: str, cwd: str, root: str) -> bool:
    """Does this process run out of `root`? An absolute path in its argv, or its own cwd.

    THE SECOND ARM IS DELIBERATELY BROADER THAN `reap.py:_placed_under`, WHICH REJECTED IT.
    That file needs to name a SERVER and found that a bare working directory also selected
    `make`, the shell around it and the session itself — too broad for something that sends a
    signal on the strength of the answer. Here "merely working in the tree" is the subject: the
    incident this exists for was `bash scratchpad/autodrive.sh`, whose argv carries no path
    under any checkout at all. The narrowing is done by the caller's own process table, not by
    placement, and the two files therefore ask the same question for different reasons.
    """
    for raw in _ABS_PATH_RE.findall(command):
        if _under(_real(raw), root):
            return True
    return bool(cwd) and _under(cwd, root)




# -------------------------------------------------------------------------- the clone


















# ---------------------------------------------------------------------------- the sweep







def teardown(tree: str, sessions_dir: Path) -> int:
    """Stop what a leaving session started in `tree`, and nothing else.

    THE MAIN CHECKOUT IS NEVER TOUCHED, WHICH IS THE WHOLE OF D138 RESPECTED. `make up` there is
    the owner's product, kept alive at login by a launch agent, serving their real store; it is
    SUPPOSED to outlive every session. In a linked worktree the same behaviour is the leak this
    tool exists for: the supervisor outlives the session, then the tree, then loops forever.

    A TREE SOMEBODY ELSE IS STILL IN IS LEFT ALONE. Two sessions can stand in one worktree, and
    the one leaving does not get to stop the other one's server.

    It never touches the branch or the tree — another session may hold either, and the sweep
    re-checks both later with the oracle anyway.
    """
    tree = _real(tree)
    if not Path(tree).is_dir():
        return 0
    if (Path(tree) / ".git").is_dir():
        say("session-teardown: main checkout — its server is the product, left alone.")
        return 0
    if not (Path(tree) / ".git").is_file():
        return 0

    # THE LEAVING SESSION IS ITS OWN ANCESTOR, NOT ITS OWN PID, AND THAT IS WHAT MADE THIS A
    # NO-OP. This runs from the leaving session's SessionEnd hook, so `os.getpid()` is this
    # Python process — a grandchild of the `claude` process whose record still sits in
    # `~/.claude/sessions`. Comparing the two pids could never match, so the leaving session
    # counted as "somebody else still here" and the teardown declined to stop anything, every
    # time. The shape of the answer is to exclude the sweep's own
    # CHAIN. Anything unreadable still keeps the servers up — `_chain` over an empty table
    # yields this pid alone, which is the old behaviour and the cautious one.
    mine = os.getpid()
    family = set(_chain(_process_tree(), mine))
    family.add(mine)
    others = [s for s in sessions_in(live_sessions(sessions_dir).sessions, tree)
              if s.pid not in family]
    if others:
        say("session-teardown: {0} session(s) still here — leaving the server up.".format(
            len(others)))
        return 0

    serve = Path(tree) / "scripts" / "serve.py"
    if serve.is_file():
        # `serve.py down` is the tested path and clears the pidfiles it wrote. It drains, so
        # it can be slow; the hook that calls this carries a raised timeout, and anything it
        # fails to finish is reaped by the claude-settings sweep later.
        got = run([sys.executable, str(serve), "down"], cwd=tree)
        say("session-teardown: {0}".format("servers stopped" if got.ok else "nothing to stop"))
        return 0

    # No Banchi supervisor here. Signalling an unknown repo's processes is a bigger claim than
    # this tool has evidence for, so it says what it found and stops.
    running = servers_under(tree, family)
    if running:
        say("session-teardown: {0} process(es) still running out of this tree; not mine to "
            "stop.".format(len(running)))
    return 0






def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="janitor",
        description="Stop what a leaving session started in one worktree.",
    )
    parser.add_argument("--teardown", metavar="TREE", required=True,
                        help="stop what a leaving session started in TREE, and nothing else. "
                             "What the SessionEnd / WorktreeRemove hook runs.")
    parser.add_argument("--sessions", default="",
                        help="where to read the liveness oracle. What scripts/janitor-selftest.sh "
                             "drives.")
    args = parser.parse_args(argv)
    return teardown(args.teardown, Path(args.sessions) if args.sessions else SESSIONS_DIR)


if __name__ == "__main__":
    sys.exit(main())
