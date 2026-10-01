#!/usr/bin/env python3
"""What a finished session leaves behind that only this repo can clean: its supervisor, its
stale registrations, its husks, and its merged branches (D111, cleanup is a sweep).

claude-settings' `janitor/sweep.py` owns the rest: dead-rooted servers, loose processes, and
tier 2 (worktrees, branches, processes). `make janitor` runs it. What stays here is the part
`sweep.py` has no mode for. It cannot press tier 1 alone, cut branches alone, or stop one tree's
supervisor with `serve.py down` (D138, the supervisor's job).

THE SAFETY RULE (D44, provably dead or reported): a thing is reaped only when nothing can be
live in it. Liveness is read from `~/.claude/sessions/<pid>.json` and from a worktree's own lock,
never from mtimes. See `_same_process` for why an unreadable case resolves to LIVE.

    scripts/janitor.py                     preview tier 1. Presses nothing.
    scripts/janitor.py --tier1             press tier 1: registrations and husks. What a hook runs.
    scripts/janitor.py --confirm           the same, from a person.
    scripts/janitor.py --branches          preview the merged-branch cut. With --confirm, cut.
    scripts/janitor.py --teardown TREE     stop that tree's servers. What the hook runs.
    scripts/janitor.py --root PATH         another checkout. Repo-agnostic on purpose.
    scripts/janitor.py --sessions DIR      read the liveness oracle elsewhere, for the self-test.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, NamedTuple, Optional, Sequence, Set, Tuple

WIDTH = 76
SESSIONS_DIR = Path.home() / ".claude" / "sessions"

# A directory that once held a worktree and now holds only this is a husk: the supervisor that
# outlived it recreates `.serve/` every few seconds, so the directory keeps coming back until
# the process is gone. Nothing here is a source file and nothing here is unrecoverable.
HUSK_NAMES = {".serve", ".vite", "node_modules", ".ruff_cache", "__pycache__"}

# Every absolute path in a command line. `ps -o command=` prints the argv space-joined, so a
# path containing a space cannot be recovered — which is why a miss is silent rather than a
# mis-parse, and why nothing here reaps on the strength of a path it could not resolve.
_ABS_PATH_RE = re.compile(r"(/[^\s]+)")

# A branch this sweep will not consider under any flag, whatever its merge state.
_NEVER_CUT = ("main", "master", "HEAD")


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
    answers with the resolved spelling while a session record and a `--confine` argument
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


def rule(title: str = "") -> None:
    print(("— " + title + " ").ljust(WIDTH, "—") if title else "—" * WIDTH)


def refuse(*lines: str) -> int:
    print("")
    print("REFUSED: " + lines[0])
    for line in lines[1:]:
        print("  " + line if line else "")
    print("")
    return 1


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
    `loose_processes` had the answer already: exclude this process and every ancestor of it.

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


def _working_dirs(pids: Set[int]) -> dict:
    """{pid: working directory} for these pids, from one BOUNDED `lsof`.

    Bounded on purpose. `reap.py` asks `lsof` for the whole machine because a kill's targets
    can be anywhere; here the candidates are the processes under one tree, a
    handful, and `make status` runs this sweep whenever somebody types it. Measured over six
    pids on this machine: 97 ms.
    """
    if not pids:
        return {}
    got = run(["lsof", "-a", "-d", "cwd", "-p", ",".join(str(p) for p in sorted(pids)), "-Fpn"])
    found = {}  # type: dict
    if not got.out:
        return found
    who = 0
    for line in got.out.splitlines():
        if line.startswith("p"):
            try:
                who = int(line[1:])
            except ValueError:
                who = 0
        elif line.startswith("n") and who:
            found.setdefault(who, _real(line[1:]))
    return found


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

class Tree(NamedTuple):
    path: str
    branch: str
    locked: bool = False
    lock: str = ""      # the lock's own reason, or "" when it was locked without one



def _lock_text(tree: str, porcelain: str) -> str:
    """A lock's reason, read from the file git keeps it in, falling back to the porcelain line.

    THE FILE IS PREFERRED BECAUSE THE PORCELAIN LINE CANNOT CARRY A NEWLINE. `git worktree list
    --porcelain` prints `locked <reason>` on one line and the reason is free text, so a
    multi-line reason runs off the end of its own record and the remainder parses as whatever
    attribute it happens to resemble. `$GIT_COMMON_DIR/worktrees/<name>/locked` holds the same
    text with no framing at all, and a linked tree names that directory in its own `.git` file.
    """
    marker = Path(tree) / ".git"
    try:
        if marker.is_file():
            head = marker.read_text(encoding="utf-8").strip()
            if head.startswith("gitdir:"):
                text = (Path(head[len("gitdir:"):].strip()) / "locked").read_text(
                    encoding="utf-8").strip()
                if text:
                    return text
    except OSError:
        pass
    return porcelain


def worktrees(root: str) -> List[Tree]:
    """Every registered working tree of this clone, main included — AND WHETHER IT IS LOCKED.

    THE LOCK IS A SECOND LIVENESS SIGNAL, ALREADY ON DISK, AND NOTHING HERE READ IT UNTIL
    2026-09-19. `live_sessions` is an oracle about SESSIONS, and a session that spawns agents
    registers ONE `cwd`: measured on this clone, pid 95092's record named
    `worktrees/app-tasks-architecture-61dc78` while its locks held
    `worktrees/agent-a27760bcdfc77fa9a` as well, and pid 2423's record named one tree while its
    locks held two others. `sessions_in` could not see those trees under any reading of the
    records, so the sweep printed `reaped ... (no session, nothing uncommitted)` over two trees
    a live process had claimed — one of them carrying two uncommitted files. The only thing
    between that sentence and the act was `git worktree remove`'s own refusal, which is
    somebody else's guard and therefore not coverage.

    THE PARSE IS RECORD-BASED RATHER THAN LINE-BASED, and that is the lock's doing. The old
    loop cleared its cursor the moment it saw `branch` or `detached`, so an attribute printed
    AFTER those — which `locked` and `prunable` both are — could never be attributed to the
    tree it belonged to. There was no line to add.
    """
    got = run(["git", "worktree", "list", "--porcelain"], cwd=root)
    if not got.ok:
        return []
    trees = []  # type: List[Tree]
    here = ""
    branch = ""
    locked = False
    lock = ""

    def flush() -> None:
        if here:
            trees.append(Tree(here, branch, locked, _lock_text(here, lock) if locked else ""))

    for line in got.out.splitlines() + [""]:
        if line.startswith("worktree "):
            flush()
            here = _real(line[len("worktree "):].strip())
            branch, locked, lock = "", False, ""
        elif line.startswith("branch "):
            branch = line[len("branch refs/heads/"):].strip()
        elif line.startswith("locked"):
            locked = True
            lock = line[len("locked"):].strip()
        elif not line.strip():
            flush()
            here, branch, locked, lock = "", "", False, ""
    return trees


def main_checkout(root: str) -> str:
    """The main working tree of this clone — the one whose `.git` is a directory."""
    got = run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=root)
    return _real(str(Path(got.out).parent)) if got.ok and got.out else ""


def default_branch(root: str) -> str:
    for name in ("main", "master"):
        if run(["git", "rev-parse", "--verify", "--quiet", "refs/heads/" + name], cwd=root).ok:
            return name
    return ""


def husks(root: str, live_roots: Set[str]) -> List[str]:
    """Directories under `.claude/worktrees/` that git no longer knows about.

    `git worktree prune` CANNOT CLEAR THESE AND THAT IS NOT A BUG IN GIT. Prune removes a
    REGISTRATION whose directory is gone; a husk is the opposite — a directory whose
    registration is gone. Three were found on 2026-09-06 holding one `capture.log` each, and
    they regenerated on their own until the supervisor writing them was stopped, which is why
    a husk with anything running under it is never in the reaped list.
    """
    base = Path(root) / ".claude" / "worktrees"
    if not base.is_dir():
        return []
    found = []  # type: List[str]
    for entry in sorted(base.iterdir()):
        if not entry.is_dir() or _real(str(entry)) in live_roots:
            continue
        try:
            contents = {child.name for child in entry.iterdir()}
        except OSError:
            # A directory this sweep cannot read is not one it may delete, and an unhandled
            # traceback here takes tier 1 down with it — including the orphan reaping that runs
            # unattended at every session end.
            continue
        if contents and contents <= HUSK_NAMES:
            found.append(_real(str(entry)))
    return found


class Kept(NamedTuple):
    branch: str
    why: str
    tell: bool     # worth a line, or ordinary bookkeeping the operator need not read


def reapable_branches(root: str, held: Set[str]) -> Tuple[List[str], List[Kept]]:
    """(branches that are provably redundant, branches that are kept and why).

    THE TEST IS ANCESTRY, NOT `git branch -d`, AND merge-pr.py IS WHERE THAT WAS ARGUED.
    `-d` refuses a branch that is behind its own upstream — "not yet merged to
    refs/remotes/origin/<branch>" — and a branch whose remote was deleted by the merge reads
    exactly that way. Every one of the 37 branches this was written for was in that state. The
    ancestor test is the STRONGER claim, so it stands in for `-d` rather than beside it.
    """
    base = default_branch(root)
    if not base:
        return [], []
    got = run(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"], cwd=root)
    if not got.ok:
        return [], []
    cut, kept = [], []  # type: List[str], List[Kept]
    for branch in got.out.splitlines():
        branch = branch.strip()
        if not branch or branch in _NEVER_CUT or branch == base:
            continue
        if branch.startswith("backup/"):
            kept.append(Kept(branch, "named backup/ — this sweep never considers one", True))
            continue
        if branch in held:
            kept.append(Kept(branch, "checked out in a working tree", False))
            continue
        if not run(["git", "merge-base", "--is-ancestor", branch, base], cwd=root).ok:
            count = run(["git", "rev-list", "--count", base + ".." + branch], cwd=root).out
            on_remote = run(
                ["git", "for-each-ref", "--format=%(refname:short)", "--contains", branch,
                 "refs/remotes/"], cwd=root,
            ).out
            # A branch main does not carry AND no remote carries exists on this disk and
            # nowhere else. That is the one this sweep most needs to say out loud: on
            # 2026-09-06 it was `backup/logo-lockup-prerebase`, 47 commits, and a cleanup that
            # took it would have destroyed all of them.
            first = on_remote.splitlines()[0] if on_remote else ""
            where = "on {0}".format(first) if first else "ON NO REMOTE — it is only on this disk"
            kept.append(Kept(
                branch,
                "{0} commit(s) {1} is missing, {2}".format(count, base, where),
                not first,
            ))
            continue
        cut.append(branch)
    return cut, kept


# ---------------------------------------------------------------------------- the sweep

def _relative(path: str, root: str) -> str:
    try:
        return str(Path(path).relative_to(root)) or "."
    except ValueError:
        return path


def sweep(root: str, sessions_dir: Path, press: bool) -> Tuple[int, int, int]:
    """(reaped, reported, pending). Tier 1 only: stale registrations and husks.

    Pressed by `--tier1` (what `session-teardown.sh` runs) and `--confirm`; a bare run previews
    and changes nothing, which is what `status.py` and the header promise. Dead-rooted servers,
    loose processes and tier 2 (worktrees, branches, processes) are claude-settings'
    `janitor/sweep.py`. `pending` is always 0: tier 1 waits on no human word.
    """
    mine = os.getpid()
    oracle = live_sessions(sessions_dir)
    sessions = oracle.sessions
    trees = worktrees(root)
    main_tree = main_checkout(root)
    live_roots = {tree.path for tree in trees}

    # ONE SAMPLE OF THE PROCESS TABLE FOR THE WHOLE SWEEP. Every placement question below is
    # asked against this and not against a fresh `ps`, so two trees judged a second apart are
    # judged against the same machine. Measured on this one: 936 processes, and the `lsof` that
    # gives them their working directories costs 0.49 s once, against roughly 30 ms per `ps`
    # multiplied by every tree and every husk in the old build.
    table = _process_table()
    dirs = _working_dirs({pid for pid, _ in table})
    # The sweep's own chain, for `servers_under`'s reason. `_process_tree` is a second `ps`
    # because only it carries the parent link; `loose_processes` computes its own for the same
    # reason and the two agree because nothing between them presses anything.
    family = set(_chain(_process_tree(), mine))
    family.add(mine)

    reaped = reported = pending = 0
    verb1 = "reaped   " if press else "would reap"

    pruned = run(["git", "worktree", "prune", "-v"] + ([] if press else ["--dry-run"]), cwd=root)
    for line in pruned.out.splitlines():
        if line.strip():
            say("  {0} registration — {1}".format(verb1, line.strip()))
            reaped += bool(press)
            reported += not press

    # A husk is removed only once nothing is running under it — they regenerate otherwise.
    for husk in husks(root, live_roots):
        # THE SESSION ORACLE IS ASKED HERE TOO, AND IT WAS NOT. A husk is a directory whose
        # REGISTRATION is gone, which is exactly what a session standing in a pruned worktree
        # is left holding — and `servers_under` alone was the only thing consulted, so one
        # liveness source stood in for the whole question on the one path that deletes a
        # directory with no confirmation at all.
        who = sessions_in(sessions, husk)
        if who:
            say("  KEPT      {0}".format(_relative(husk, root)))
            say("            a session is live in it ({0})".format(
                ", ".join(s.name or str(s.pid) for s in who)))
            reported += 1
            continue
        if servers_under(husk, family, table, dirs):
            say("  KEPT      {0}".format(_relative(husk, root)))
            say("            a process is still running under it; it would come back")
            reported += 1
            continue
        if not press:
            say("  {0} {1}  (husk — no registration, no source)".format(
                verb1, _relative(husk, root)))
            reported += 1
            continue
        shutil.rmtree(husk, ignore_errors=True)
        if Path(husk).exists():
            # `ignore_errors=True` swallows a permission failure whole, so the old build printed
            # `reaped` over a directory that is still there. Look, then speak.
            say("  NOT REAPED {0}".format(_relative(husk, root)))
            say("            the directory is still on disk")
            reported += 1
            continue
        say("  reaped    {0}  (husk — no registration, no source)".format(_relative(husk, root)))
        reaped += 1

    return reaped, reported, pending


def cut_merged_branches(root: str, confirm: bool) -> Tuple[int, int]:
    """(cut, kept). Tier 2's ONE provably-lossless act, and nothing else in tier 2.

    THE SUBSET THAT NEEDS NO HUMAN WORD, WHICH IS WHY IT CAN RUN FROM A HOOK. Tier 2 does three
    things: it stops loose processes, it removes worktrees, and it cuts branches. The first two
    are judgement calls about what somebody might still be using. The third is not. A branch
    reaches `reapable_branches`' `cut` list only when main is a descendant of every commit on it
    — `git branch -D` there removes a label and destroys nothing, because every object it named
    is reachable from main. That is the same ancestry test `make janitor ARGS=--confirm`
    already runs, called here and not reimplemented.

    SO THE WORD TIER 2 WAITS ON IS ABOUT THE OTHER TWO. Deleting a worktree can cost uncommitted
    work the sweep failed to see, and stopping a process can cost a run somebody wanted. Neither
    risk exists here, and holding a lossless act behind the same word as a lossy one is what
    left nine merged branches sitting on this disk with nobody to press it.

    IT FAILS CLOSED ON A LAYOUT IT CANNOT READ, which is the whole of the protection. `held`
    comes from `git worktree list`; an unreadable one returns no trees, every branch loses the
    protection a checked-out tree gives it, and a branch somebody is standing on becomes
    eligible. The full sweep already refuses in that state and so does this, by the same test.

    NOTHING HERE REMOVES A TREE, so `held` is every worktree's branch with nothing subtracted.
    The full sweep lets a branch out of `held` when it is about to remove that branch's tree;
    this never removes one, so it never lets one out. That is the safe direction by
    construction rather than by care.
    """
    trees = worktrees(root)
    if not trees or not main_checkout(root):
        say("  KEPT      every branch — this clone's own layout is unreadable")
        return 0, 1
    held = {tree.branch for tree in trees if tree.branch}
    cut, kept = reapable_branches(root, held)
    if not cut:
        return 0, 0
    done = 0
    for branch in cut:
        if not confirm:
            say("  would reap {0}  (merged, no working tree)".format(branch))
            continue
        gone = run(["git", "branch", "-D", branch], cwd=root)
        say("  {0} {1}".format("reaped   " if gone.ok else "NOT CUT  ", branch))
        if gone.ok:
            done += 1
    return done, len(cut) - done


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
    # time. `loose_processes` already had the shape of the answer: exclude the sweep's own
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
        # fails to finish is reaped by `--tier1` on a later sweep.
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="janitor",
        description="Reap the worktrees, branches and servers a finished session left behind.",
    )
    parser.add_argument("--root", default="", help="the checkout to sweep. Defaults to this one.")
    parser.add_argument("--confirm", action="store_true",
                        help="press tier 1 (and, with --branches, the cut). Without it, a preview.")
    parser.add_argument("--branches", action="store_true",
                        help="cut every branch main already carries, and do nothing else. "
                             "The one part of tier 2 that destroys nothing, so it needs no "
                             "word and a hook may run it. Previews without --confirm.")
    parser.add_argument("--tier1", action="store_true",
                        help="the provably-dead only — no preview, no prompt. What a hook runs.")
    parser.add_argument("--sessions", default="",
                        help="where to read the liveness oracle. What scripts/janitor-selftest.sh "
                             "drives.")
    parser.add_argument("--teardown", metavar="TREE", default="",
                        help="stop what a leaving session started in TREE, and nothing else. "
                             "What the SessionEnd / WorktreeRemove hook runs.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.teardown:
        return teardown(
            args.teardown,
            Path(args.sessions) if args.sessions else SESSIONS_DIR,
        )

    start = args.root or os.getcwd()
    found = run(["git", "rev-parse", "--show-toplevel"], cwd=start)
    if not found.ok:
        return refuse(
            "{0} is not a git repository.".format(start),
            "",
            "This sweep reads a clone's own worktrees and branches, so there has to be one.",
        )
    root = _real(found.out)
    sessions_dir = Path(args.sessions) if args.sessions else SESSIONS_DIR

    if args.branches:
        cut, kept = cut_merged_branches(root, args.confirm)
        if cut or kept:
            say("janitor: {0} branch(es) cut, {1} reported".format(cut, kept))
        return 0

    if args.tier1:
        reaped, reported, _ = sweep(root, sessions_dir, True)
        if reaped or reported:
            say("janitor: {0} reaped, {1} reported".format(reaped, reported))
        return 0

    say("JANITOR — {0}{1}".format(root, "" if args.confirm else "  (PREVIEW)"))
    rule()
    reaped, reported, pending = sweep(root, sessions_dir, args.confirm)
    rule()
    say("janitor: {0} reaped, {1} reported{2}".format(
        reaped, reported,
        "" if not pending else "  ({0} waiting on --confirm)".format(pending),
    ))
    # Only work waiting on a word is worth an exit code. Information is not a finding.
    return 1 if pending else 0


if __name__ == "__main__":
    sys.exit(main())
