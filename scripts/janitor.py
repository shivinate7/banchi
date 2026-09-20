#!/usr/bin/env python3
"""Find — and, where it is provably safe, reap — the exhaust a finished session leaves behind.

WHY THIS EXISTS. On 2026-09-06 this clone held seven worktrees, 73 local branches and four
supervisor processes whose working trees had been deleted out from under them — one had been
restarting against a directory that no longer existed since 2026-09-03. Cleaning it by hand
reclaimed 334M and took the branches to nine. None of that was a one-off: 37 of the branches
sat in the IDENTICAL state — merged, deleted at origin, alive here — because `merge-pr.py`
deletes the head branch at origin unconditionally and skips the local half whenever a worktree
holds it, which is true by construction when a session merges its own PR from its own tree.
The origin half succeeded 37 times; the local half was refused 37 times, and nothing ever came
back to ask again.

SO THE FIX IS A SWEEP AND NOT A HOOK ON THE MERGE. Cleanup was attached to events that fire
BEFORE the thing being cleaned is releasable — the merge waits on the tree, the tree waits on
the session, the session ends with no teardown, and the supervisor waits on nobody. Each
layer's cleanup is conditional on a layer above it already being gone, and nothing re-checks.
Only something re-runnable at an arbitrary moment can collect what a one-shot structurally
could not.

THE SAFETY RULE, AND IT IS THE WHOLE DESIGN, INHERITED FROM D44: a thing is reaped only when
it is provably dead. Anything else is REPORTED and left alone. The two are separate lists and
only one of them has a removal path, so there is no flag and no argument that can walk a
doubtful case into a delete — the same asymmetry `icloud-sweep.py` is built on, taken
deliberately rather than reinvented.

LIVENESS IS READ FROM EVERY PLACE IT IS WRITTEN, AND THERE ARE TWO. The console app keeps one
answer in `~/.claude/sessions/<pid>.json`; git keeps the other in a worktree's own `locked`
file. Neither is complete. A session that spawns agents registers ONE `cwd` and locks SEVERAL
trees — measured on this clone 2026-09-19: one live session's record named one worktree while
its locks held three — so the records alone said "no session" over trees a live process had
claimed, and the sweep printed `reaped` over two of them. `worktrees` reads the lock and
`_lock_lines` reports it; a locked tree is never a candidate.

LIVENESS IS READ, NEVER GUESSED. File mtimes and `git status` cannot tell a live worktree from
a dead one: on the day this was written two trees showed zero dirty files and no recent writes,
then switched branches while they were being measured. The console app already keeps the
answer in `~/.claude/sessions/<pid>.json` — a `cwd` and a `pid`, checked alive, and checked
against `startedAt` so a recycled pid cannot inherit a dead session's claim on a tree. See
`_same_process` for why that comparison is made on the epoch and never on the `procStart`
string beside it, and for why every unreadable case resolves to LIVE.

IDENTITY IS AN ABSOLUTE PATH, NEVER A PID AND NEVER A PORT. Pids churn — D53's supervisor
re-execs and its children are replaced, twice inside twenty minutes on the day this was
written — and `started_at` in a pidfile is rewritten by that re-exec, so it is not process age.
The port cannot be inverted: it is `sha256(path)[:4] % 300`, one-way, and 300 slots collide.

IT IS NOT IN `make check` AND NOT IN THE GIT HOOK. D18 at its strongest, exactly as D44 argues
for `icloud-sweep`: this and that are the only two targets in this repo that can delete a file,
and nothing that writes may run on the path that decides whether a commit proceeds. Its
SELF-TEST gates, and does not write outside a temp directory. `make status` reports the count,
which is where a fact you should know but need not act on belongs.

    scripts/janitor.py                     preview this repo. Presses nothing — and since
                                           2026-09-19 that is true: tier 1 used to run here.
    scripts/janitor.py --confirm           reap tier 2 as well as tier 1.
    scripts/janitor.py --tier1             the provably-dead only, no prompt. What a hook runs.
    scripts/janitor.py --root PATH         another checkout. Repo-agnostic on purpose.
    scripts/janitor.py --teardown TREE     stop that tree's servers. What the hook runs.
    scripts/janitor.py --sessions DIR      read the liveness oracle elsewhere, for the self-test.
    scripts/janitor.py --stale-hours N     when a process a session still owns is worth a line.

AND OWNERSHIP IS READ THE SAME WAY LIVENESS IS. The records above answer a second question this
file could not ask until 2026-09-12: not "is this tree busy" but "does anything still own this
PROCESS". Everything else here is about a tree, a branch or a registration, and tier 1's test is
"can this be live at all" — so a background loop whose session has ended read as live, leave it
alone. One ran for 3 h 58 m merging pull requests out from under its own successor session, and
nothing in this repo could see it. `loose_processes` is that question; it names only what it can
PROVE a session started, and it can never name the main checkout's server.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
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

# THE BASH TOOL'S OWN WRAPPER IS WHAT MAKES SESSION ORIGIN PROVABLE, AND IT IS THE WHOLE REASON
# `loose_processes` is allowed to name anything at all. Every command a Claude Code session runs
# arrives as `zsh -c 'source ~/.claude/shell-snapshots/snapshot-zsh-<n>-<id>.sh ... && <command>'`,
# so this fragment sits in that wrapper's argv — and stays there after the session that wrote it
# is gone, because a reparented process keeps the argv it was exec'd with. Measured on this
# machine 2026-09-12: it appears in the wrapper of every session-started process and in nothing
# else, and notably NOT in `scripts/serve.py run`, which launchd starts from a plist.
_SESSION_MARK = os.path.join(".claude", "shell-snapshots")

# How long a process a live session still claims may run before it is worth a LINE — never a
# reap; see `loose_processes` for why that half is reported and never offered.
#
# DERIVED, NOT PICKED. Measured 2026-09-12 on this machine: the ten live session records ran
# 0.78 h to 23.89 h, median 13.05 h, and a `make dev` Vite server owned by a session is
# legitimate for the whole of its session's life — so anything at or under a day is a number
# that fires on healthy work. The foreground commands are nowhere near it: `make check` ~17 s,
# `make harness` ~13 s, `make design-check` 89-175 s over five runs. 48 h is twice the longest
# session measured, and it also sits ABOVE the 37.1 h the owner's rig supervisor had been up
# when this was written — so even with every exclusion below broken, the clock alone could not
# have named that process.
STALE_HOURS = 48.0


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


def _project_ancestor(path: Path) -> str:
    """The project a missing path belonged to, or "" if it belonged to none.

    THE SCOPE OF THE WHOLE SWEEP IS THIS FUNCTION. A process referring to a path that does not
    exist is an ordinary thing on a Mac and most of them are nobody's business; what makes one
    ours is that the path sat inside a checkout or inside a worktree directory. Walking up to
    the first existing ancestor and asking whether anything above it carries a `.git` or a
    `.claude` is the narrowest test that still catches a supervisor whose whole tree was
    deleted, which is the case this exists for.
    """
    for parent in path.parents:
        if not parent.exists():
            continue
        probe = parent
        for _ in range(12):
            if (probe / ".git").exists() or (probe / ".claude").is_dir():
                return str(probe)
            if probe.parent == probe:
                break
            probe = probe.parent
        return ""
    return ""


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


def dead_rooted_servers(mine: int, confine: str = "",
                        table: Optional[Sequence[Tuple[int, str]]] = None) -> List[Server]:
    """Processes still running out of a directory that is gone.

    `confine` narrows the hunt to one subtree. It is empty in every real run — an orphan's
    whole point is that its tree is gone, and a deleted sibling checkout resolves to a project
    directory ABOVE the repo being swept, so a sweep that confined itself to its own root would
    miss exactly the case it exists for. It is what scripts/janitor-selftest.sh drives, so that
    the self-test signals its own fixture and never a real process on the machine.

    A RESTART LOOP AGAINST A DELETED FILE CANNOT BE LIVE, WHICH IS WHY THIS IS TIER 1. Four of
    these were found on 2026-09-06, the oldest running since 2026-08-30, each one failing to
    launch a `capture_server.py` in a tree that had been removed and each one recreating the
    `.serve/` directory it logged the failure into. They held no port and served nothing.

    The test is the process's OWN argv naming a file that does not exist — not its cwd, which
    on that day still existed precisely because the loop kept recreating it.
    """
    found = []  # type: List[Server]
    for pid, command in (_process_table() if table is None else table):
        if pid == mine:
            continue
        for raw in _ABS_PATH_RE.findall(command):
            candidate = Path(raw)
            if candidate.suffix not in (".py", ".mjs", ".js", ".sh", ".ts"):
                continue
            if candidate.exists():
                continue
            # Resolved before comparing, for _real's reason: `ps` echoes back whatever the
            # caller typed, and every path this file compares it against has been resolved.
            token = _real(raw)
            if confine and not (token == confine or token.startswith(confine + os.sep)):
                continue
            home = _project_ancestor(candidate)
            if not home:
                continue
            found.append(Server(pid, command, token, home))
            break
    return found


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


# ------------------------------------------------- the process nothing owns any more (D175)

class Loose(NamedTuple):
    pid: int
    command: str
    tree: str         # the working tree of this clone it runs out of
    hours: float      # how long it has been up, or -1.0 when `ps` could not be read
    owner: str        # the live session that started it, or "" when none does


class Scan(NamedTuple):
    """What the hunt for loose processes found, AND WHAT IT LOOKED AT.

    `examined` is here because a sweep that enumerated nothing must not print the same word as
    one that read the whole process table and found everything owned. That confusion is this
    repo's signature defect — `corpus_is_empty` exists in `docs-audit.py` for it — and it is
    worse here than anywhere: "nothing loose" is the sentence a session would read as proof that
    the four-hour loop of 2026-09-11 was not running, and a `ps` that failed prints it too.
    """
    offered: List[Loose]
    reported: List[Loose]
    examined: int     # session-started processes placed under this clone
    owned: int        # of those, how many a live session still claims


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
    can be anywhere; here the candidates have already been narrowed by `_SESSION_MARK` to a
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
    under any checkout at all. The narrowing is done by `_SESSION_MARK` and by ownership, not by
    placement, and the two files therefore ask the same question for different reasons.
    """
    for raw in _ABS_PATH_RE.findall(command):
        if _under(_real(raw), root):
            return True
    return bool(cwd) and _under(cwd, root)


def loose_processes(root: str, main_tree: str, trees: Sequence[Tree],
                    sessions: Sequence[Session], mine: int, stale_hours: float) -> Scan:
    """The processes a session started out of this clone that nothing is listening to.

    THE HOLE THIS FILLS. Every other test in this file is about a TREE, a BRANCH or a
    REGISTRATION, and tier 1's question is "can this be live at all". A running background loop
    is none of those and answers that question with a yes, so a running pid read as "live, leave
    it alone". The guard could tell a dead process from a live one and could not tell a live
    process from an OWNED one. On 2026-09-11 that cost 119 rounds over 3 h 58 m: a coordinator
    backgrounded a merge driver, was compacted, and the loop went on merging pull requests out
    from under its own successor. Nothing in this repo could see it; the owner noticed a
    four-hour `bash` in their UI and asked.

    OWNERSHIP IS READ THE WAY LIVENESS IS, WHICH IS THE WHOLE POINT: the same
    `~/.claude/sessions` records, pointed at a different question. Not "is this tree busy" but
    "does anything still own this process". A process is owned when a LIVE session's pid is in
    its parent chain, and that is measured rather than assumed — on this machine every process
    of every live session traced back to its own session's pid, and the only two that traced to
    nothing were the rig supervisor and its capture child.

    IT NAMES ONLY WHAT IT CAN PROVE A SESSION STARTED, AND THAT ASYMMETRY IS THE SAFETY. Absence
    of a session record is NOT evidence of absence of an owner: `~/.claude/sessions` is an oracle
    about SESSIONS, and a process the OWNER started by hand in a terminal has no record either.
    So the test is positive — `_SESSION_MARK` in the process's own argv or an ancestor's — and
    anything that cannot be shown to have come from a session is passed over in silence. That is
    `reap.py:hook`'s rule in this file's terms: a broken guard fails open, an unreadable target
    fails closed.

    AND IT CAN NEVER NAME THE MAIN CHECKOUT'S SERVER, BY CONSTRUCTION RATHER THAN BY SUBTRACTION.
    Being inside a LINKED worktree is a requirement to be offered at all, not an exclusion
    applied afterwards, so there is no ordering, no `continue` and no failed `main_checkout()`
    lookup that can let the rig through. D53 means that process to outlive every session, it has
    no session record by design, and a rule that offered it up would be wrong however carefully
    the rest of it read — this repo has already killed it once with `pkill -f` (D127). The cost
    of the requirement is a real and named gap: a loop backgrounded from a session standing in
    the main checkout is not caught. That is the safe half of the trade and it is the entry's
    reopening condition.

    TWO FINDINGS, AND ONLY ONE OF THEM IS EVER OFFERED:

      * NO LIVE OWNER — offered, and pressed only on `--confirm`. Tier 2, not tier 1, and the
        entry argues it: `sweep` reaps tier 1 before it looks at `confirm` at all, so `make
        status` — which runs the bare sweep — would have SIGTERMed these with no preview and
        no prompt. That ordering is fixed as of 2026-09-19 and this placement is still right:
        `--tier1` presses whatever tier 1 holds, unattended, at every session end.
      * STILL OWNED BUT OLDER THAN `STALE_HOURS` — reported, and never reaped under any flag.
        A live session claims it, and a sweep does not get to kill something whose owner is
        sitting right there to be asked.
    """
    table = _process_tree()
    if not table:
        # A `ps` that failed is this guard being broken about itself, so it fails OPEN — nothing
        # is named. `examined` of 0 is what keeps that from reading as an all-clear.
        return Scan([], [], 0, 0)

    live = {s.pid for s in sessions}
    named = {s.pid: (s.name or str(s.pid)) for s in sessions}

    # THE SWEEP'S OWN CHAIN IS NEVER A CANDIDATE, AND THIS IS NOT BELT AND BRACES. `make janitor`
    # runs from a session's Bash wrapper, so this process carries `_SESSION_MARK` and runs out of
    # a linked worktree — it is its own subject. It reads as owned only while its own session
    # record is readable, and D111 records what happened the one time that oracle returned
    # nought: the sweep offered up the tree it was running in.
    family = set(_chain(table, mine))

    linked = [t.path for t in trees if t.path != main_tree]
    # A worktree git has already forgotten is still a worktree — `husks` exists because a
    # directory can outlive its registration, and a process under one must not read as the
    # main checkout's merely because `git worktree list` no longer mentions it.
    husk_base = _real(str(Path(root) / ".claude" / "worktrees"))

    started = {}  # type: dict
    for pid in table:
        if pid in family:
            continue
        walk = _chain(table, pid)
        if any(_SESSION_MARK in table[step][1] for step in walk if step in table):
            started[pid] = walk

    dirs = _working_dirs(set(started))

    offered, reported = [], []  # type: List[Loose], List[Loose]
    examined = owned = 0
    for pid in sorted(started):
        command = table[pid][1]
        cwd = dirs.get(pid, "")
        if not _placed(command, cwd, root):
            continue
        examined += 1
        tree = next((t for t in sorted(linked, key=len, reverse=True)
                     if _placed(command, cwd, t)), "")
        if not tree and _placed(command, cwd, husk_base):
            tree = husk_base
        owner = next((named[step] for step in started[pid] if step in live), "")
        owned += bool(owner)
        start = _proc_start(pid)
        # A pid `ps` will not answer for is one this sweep cannot age, so it is never judged on
        # time. -1.0 rather than 0.0: zero would read as "brand new" and be the one value that
        # silently passes the staleness test.
        hours = -1.0 if start is None else max(0.0, (time.time() - start) / 3600.0)
        found = Loose(pid, command, tree or main_tree, hours, owner)
        if not tree:
            # The main checkout, and therefore never offered whatever else is true of it. It is
            # still worth a line when nothing owns it: this is the one place the sweep says out
            # loud what it refused to touch, which is `make reap`'s standard.
            if not owner:
                reported.append(found)
            continue
        if not owner:
            offered.append(found)
        elif hours > stale_hours:
            reported.append(found)
    return Scan(offered, reported, examined, owned)


# -------------------------------------------------------------------------- the clone

class Tree(NamedTuple):
    path: str
    branch: str
    locked: bool = False
    lock: str = ""      # the lock's own reason, or "" when it was locked without one


# The pid inside a lock reason. `git worktree lock --reason` takes free text, and the one this
# machine writes is `claude agent <name> (pid 95092 start Sat Sep 19 17:22:35 2026)` — so the
# pid is READ OUT of prose rather than parsed from a field, and a reason shaped any other way
# simply yields nothing. Yielding nothing keeps the tree, which is the safe answer, so this
# regex can only ever make the sweep more cautious and never less.
_LOCK_PID_RE = re.compile(r"\bpid[\s:=#]*(\d+)\b", re.IGNORECASE)


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


def _lock_lines(tree: Tree) -> List[str]:
    """What the sweep says about a locked tree. It is KEPT either way; only the sentence moves.

    A LOCK IS SOMEBODY'S EXPLICIT CLAIM, so a dead pid does not release it. The pid is read and
    reported because an operator clearing up needs to know which of these is finished — but the
    sweep does not get to decide that a claim somebody wrote down has expired, and `git worktree
    unlock` is a person's press. Every unreadable case lands on the keep side by construction:
    no reason, no pid in the reason, and an unreadable pid all leave the tree alone.
    """
    if not tree.lock:
        return ["locked, with no reason recorded — a lock is a claim, and this sweep keeps it"]
    found = _LOCK_PID_RE.search(tree.lock)
    lines = ["locked: {0}".format(_shorten(tree.lock))]
    if not found:
        lines.append("the reason names no pid, so nothing here can say the claim is over")
        return lines
    pid = int(found.group(1))
    if _pid_alive(pid):
        lines.append("pid {0} IS ALIVE — this tree is in use".format(pid))
    else:
        lines.append("pid {0} is gone; `git worktree unlock {1}` releases it".format(
            pid, tree.path))
    return lines


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

    THE TEST IS ANCESTRY, NOT `git branch -d`, AND merge-pr.py:494 IS WHERE THAT WAS ARGUED.
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


def _stop(pid: int) -> bool:
    """SIGTERM one process, and its group ONLY WHEN IT LEADS THAT GROUP.

    A supervisor's children should go with it, and `serve.py` spawns every one
    `start_new_session=True` so each IS its own leader — but a process that is merely a MEMBER
    of somebody else's group would have that whole group signalled on its behalf, which is a
    stranger's shell and everything in it. Leader, group. Not leader, the pid alone.

    It is one function because two callers now send this signal for two different reasons — the
    orphan whose own script is gone, and the loose process nothing owns — and a guard that
    reasoned one way in one place and another way in the other is how `reap.py`'s own
    `pids_under`/`verdict_for` split produced a defect nobody could see.

    THE RETURN VALUE IS "THE SIGNAL WAS DELIVERED", NOT "THE PROCESS IS GONE", and the caller
    prints one and not the other. A process already gone counts as delivered; a process that
    refuses the signal — another user's, EPERM — counts as not, and the sweep says so rather
    than printing the word `reaped` over it.
    """
    try:
        if os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return True


def _shorten(command: str, width: int = 64) -> str:
    return command if len(command) <= width else command[:width - 1] + "…"


def sweep(root: str, sessions_dir: Path, confirm: bool, tier1: bool,
          confine: str = "", stale_hours: float = STALE_HOURS) -> Tuple[int, int, int]:
    """(reaped, reported, pending). Prints the whole account as it goes.

    THE THIRD NUMBER IS THE ONLY ONE THAT SETS AN EXIT CODE, and the distinction is the point:
    `pending` is what a `--confirm` would act on, `reported` is everything worth a line. A kept
    `backup/` branch is a fact you should know and never a thing to do, so a healthy clone with
    one in it must not fail — the first build returned 1 there and made `make janitor` print
    `Error 1` on a repo with nothing wrong with it.

    A BARE RUN PRESSES NOTHING, WHICH IS WHAT IT HAS ALWAYS CLAIMED AND DID NOT DO. The header
    above says "preview this repo. Presses nothing" and `status.py:janitor()` says "`make
    status` must never be a thing that changes the tree" — and until 2026-09-19 the tier 1
    block ran before `confirm` was ever consulted, so the bare run SIGTERMed orphans, ran `git
    worktree prune` and `rmtree`'d husks under a command that had asked for none of it. Two
    documents stating one contract and the code keeping another is not a decision anybody
    made; it is a drift.
    Tier 1 is still pressed with no prompt by whatever asks for it BY NAME — `--tier1`, which
    is what `session-teardown.sh` runs — and by `--confirm`. Nothing is lost and the word
    PREVIEW means what it says.

    THE RULE THE NEIGHBOURS KEEP IS "NAME THE ACT", NOT "PREVIEW BY DEFAULT", and it is what
    settled this (owner's word, 2026-09-19, after the convention was looked up rather than
    recalled). Every comparable tool makes the caller say the destructive word out loud before
    it presses: `git worktree prune` IS the word, and previews only under `-n`; `git gc` is the
    word; `docker system prune` is the word and still stops to ask, skippable with `-f`; `git
    clean` is the word and REFUSES anyway — `clean.requireForce` defaults to true, so it does
    nothing at all without `-f`, `-i` or `-n`, because its targets exist nowhere else. Not one
    of them does destructive work under a bare invocation that names no act.

    That is exactly what this was doing. `janitor.py` with no argument names nothing, prints
    the word PREVIEW in its own header, and signalled processes and deleted directories. The
    defect was never that tier 1 presses — it is that it pressed under a command that had not
    been asked. A prompt is the other half of the convention and is no use here: this runs from
    a SessionEnd hook and from agent sessions with nobody at the keyboard, so the flag is the
    right form, which is `git clean -f`'s answer to the same problem.

    THE ARGUMENT FOR LEAVING IT ALONE WAS A MEASUREMENT ERROR, AND IT IS RECORDED BECAUSE IT
    nearly carried the day. The case for pressing was that the bare run is a third cleanup
    trigger that does not depend on SessionEnd, which `.claude/settings.json` itself calls
    unreliable at app quit and machine sleep. It is not a trigger at all: the only SessionStart
    hook is `worktree-guard.sh`, and nothing anywhere runs `make status` or `make janitor` by
    itself. The comment that says the bare preview runs "at the head of every session" is prose
    habit, and reading it rather than the hook roster is how this argument was first made.

    TIER 1'S PREVIEW IS `reported` AND NEVER `pending`, because `pending` is the count of work
    waiting on a HUMAN word and tier 1 waits on no word at all: the session-end hook presses it
    unattended. Counting it would make `make status` ask the operator for a press that another
    hook is about to make on its own.
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
    press = confirm or tier1
    verb1 = "reaped   " if press else "would reap"

    # ---------------------------------------------------------------- tier 1: the dead
    for server in dead_rooted_servers(mine, confine, table):
        say("  {0} pid {1} — its own {2} is gone".format(
            verb1, server.pid, Path(server.missing).name))
        say("            {0}".format(server.missing))
        if not press:
            reported += 1
            continue
        if _stop(server.pid):
            reaped += 1
        else:
            say("            NOT STOPPED — the signal was refused")
            reported += 1

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

    if tier1:
        return reaped, reported, pending

    # ------------------------------------------------------- tier 2: needs a human word
    #
    # NOTHING BELOW RUNS WHILE A SUBJECT IS UNREADABLE, AND THE TWO CASES ARE THE TWO ORACLES.
    # An unparseable session record is a session this sweep cannot see, and a tree it cannot see
    # a session in is a tree it calls empty. An unreadable `git worktree list` is worse: `trees`
    # comes back empty, so every branch loses the protection `held` gives it and `main_tree`
    # comes back "" — which puts the MAIN CHECKOUT in `linked` inside `loose_processes` and
    # makes the rig supervisor D53 exists to protect offerable. Both of those failed OPEN.
    if oracle.unreadable:
        say("  KEPT      every tree, branch and process — the liveness oracle is incomplete")
        for name in oracle.unreadable:
            say("            {0} would not parse".format(name))
        say("            a record that cannot be read is a session that cannot be seen")
        return reaped, reported + 1, pending
    if not trees or not main_tree:
        say("  KEPT      every tree, branch and process — this clone's own layout is unreadable")
        say("            `git worktree list` gave {0} tree(s) and the main checkout read as "
            "{1!r}".format(len(trees), main_tree))
        return reaped, reported + 1, pending

    verb = "reaped   " if confirm else "would reap"

    # THE PROCESS NOTHING OWNS COMES FIRST, BECAUSE ITS TREE CANNOT BE REAPED WHILE IT RUNS. The
    # loop below keeps a tree that has a server running out of it, so this offer and that refusal
    # are two halves of one account: stop the process on this sweep, and the tree it was holding
    # open becomes reapable on the next. That is D111's re-runnability doing the work a one-shot
    # ordering could not.
    scan = loose_processes(root, main_tree, trees, sessions, mine, stale_hours)
    if scan.examined:
        say("  looked at {0} process(es) a session started under this clone — "
            "{1} still owned, {2} loose".format(
                scan.examined, scan.owned, len(scan.offered)))
    else:
        # NOT the same sentence as "examined everything, found nothing loose". A `ps` that
        # failed, a machine with no session-started process on it, and a healthy clone all land
        # here, and none of them is evidence that nothing is running.
        say("  looked at no process here carries a session's own shell wrapper — "
            "nothing to judge")
    for loose in scan.reported:
        say("  KEPT      pid {0}".format(loose.pid))
        say("            {0}".format(_shorten(loose.command)))
        if not loose.owner:
            say("            the MAIN CHECKOUT's — D53 means it to outlive every session")
        else:
            say("            up {0:.1f} h, and {1} still owns it — ask, do not reap".format(
                loose.hours, loose.owner))
        reported += 1
    for loose in scan.offered:
        say("  {0} pid {1}  (no live session owns it)".format(verb, loose.pid))
        say("            {0}".format(_shorten(loose.command)))
        say("            started out of {0}, up {1}".format(
            _relative(loose.tree, root),
            "an unreadable time" if loose.hours < 0 else "{0:.1f} h".format(loose.hours)))
        if not confirm:
            reported += 1
            pending += 1
        elif _stop(loose.pid):
            reaped += 1
        else:
            say("            NOT STOPPED — the signal was refused")
            reported += 1

    # ------------------------------------------------------------------------- the trees
    #
    # THE VERDICT IS COMPUTED BEFORE ANYTHING IS PRINTED OR PRESSED, AND THE BRANCHES ARE WHY.
    # `held` protects a branch a worktree is standing on, and the old build discarded a branch
    # from it INSIDE `if confirm:` — after a successful removal. On a preview no tree is
    # removed, so nothing was ever discarded, so every branch whose tree was about to go still
    # read as held and printed KEPT; on `--confirm` the same branch was discarded mid-loop and
    # became eligible to cut. The preview therefore under-reported branch deletions
    # systematically, and no amount of reading it could have revealed one:
    # `claude/claude-md-dedupe-v2` and `claude/elegant-matsumoto-d092ba` both printed
    # `ON NO REMOTE — it is only on this disk` and both were gone after the word, their commits
    # surviving as dangling objects. One plan, read twice, is the only shape that cannot do
    # that — the preview is now the confirm run with its hands tied.
    plans = []  # type: List[Tuple[Tree, Optional[List[str]]]]
    for tree in trees:
        if tree.path == main_tree:
            continue
        if tree.locked:
            plans.append((tree, _lock_lines(tree)))
            continue
        who = sessions_in(sessions, tree.path)
        if who:
            plans.append((tree, ["a session is live in it ({0})".format(
                ", ".join(s.name or str(s.pid) for s in who))]))
            continue
        dirty = run(["git", "status", "--porcelain"], cwd=tree.path)
        if not dirty.ok:
            # `dirty.ok and dirty.out` fell THROUGH to reapable when `git status` would not
            # run — a tree whose state could not be read was treated as a tree with nothing
            # in it. The direction-of-safety rule says the opposite.
            plans.append((tree, ["`git status` would not run here — "
                                 "a tree this sweep cannot read is a tree it keeps"]))
            continue
        if dirty.out:
            plans.append((tree, ["{0} uncommitted file(s) — look at them yourself".format(
                len(dirty.out.splitlines()))]))
            continue
        if servers_under(tree.path, family, table, dirs):
            plans.append((tree, ["a server is running out of it; stop it first"]))
            continue
        plans.append((tree, None))

    held = {tree.branch for tree in trees if tree.branch}
    held -= {tree.branch for tree, why in plans if why is None and tree.branch}

    for tree, why in plans:
        if why:
            say("  KEPT      {0}".format(_relative(tree.path, root)))
            for line in why:
                say("            {0}".format(line))
            reported += 1
            continue
        if not confirm:
            say("  would reap  {0}  (no session, nothing uncommitted)".format(
                _relative(tree.path, root)))
            reported += 1
            pending += 1
            continue
        # THE OUTCOME IS REPORTED AFTER THE ATTEMPT. The old build fixed the word `reaped` up
        # front and printed it before `git worktree remove` ran, so a refusal produced
        # `reaped ...` followed two lines later by `not removed — ...`: a line claiming an act
        # that did not happen, contradicting itself in the same paragraph, with the count
        # correctly excluding it so the body and the total disagreed.
        gone = run(["git", "worktree", "remove", tree.path], cwd=root)
        if gone.ok:
            say("  reaped      {0}  (no session, nothing uncommitted)".format(
                _relative(tree.path, root)))
            reaped += 1
            continue
        say("  NOT REAPED  {0}".format(_relative(tree.path, root)))
        say("            {0}".format((gone.err.splitlines() or [""])[-1]))
        reported += 1
        # The plan said this tree was going, so its branch was let out of `held`. It did not go,
        # so the branch is protected again. That is the ONE place preview and confirm may
        # differ, and it differs in the safe direction: the preview over-reports a cut, which an
        # operator reads before pressing, where the bug above under-reported one.
        if tree.branch:
            held.add(tree.branch)

    cut, kept = reapable_branches(root, held)
    for entry in kept:
        if not entry.tell:
            continue
        say("  KEPT      {0}".format(entry.branch))
        say("            {0}".format(entry.why))
        reported += 1
    for branch in cut:
        if not confirm:
            say("  would reap {0}  (merged, no working tree)".format(branch))
            reported += 1
            pending += 1
            continue
        gone = run(["git", "branch", "-D", branch], cwd=root)
        say("  {0} {1}".format("reaped   " if gone.ok else "NOT CUT  ", branch))
        if gone.ok:
            reaped += 1
        else:
            reported += 1

    return reaped, reported, pending


# ------------------------------------------------------------------- the daily sweep agent
#
# THE EVENT HALF MISSES THINGS, AND `.claude/settings.json` SAYS SO ITSELF. `SessionEnd` is
# "not reliable at app quit or machine sleep", and `WorktreeRemove` only fires when somebody
# removes a tree — an agent worktree abandoned by a session that died is removed by nobody, so
# no event ever fires for it. Measured on this clone 2026-09-20: five such trees and nine
# merged branches were waiting, some for days, with every event that could have taken them
# long past.
#
# SO THE SCHEDULE IS THE BACKSTOP, AND IT IS A BACKSTOP RATHER THAN THE MECHANISM. Everything
# it presses, the hooks would have pressed at the right moment had they fired. A sweep that
# runs whether or not an event arrived is D111's re-runnability applied to the trigger instead
# of to the sweep.
#
# GENERATED AND NEVER TRACKED, and MAIN TREE ONLY, for serve.py's two reasons verbatim: a
# plist names an absolute path on one Mac (D47), and a plist naming a worktree outlives the
# worktree, leaving launchd retrying a directory that is not there.
#
# THE LOG IS THE RECEIPT, AND IT IS THE WHOLE OF WHAT MAKES AN UNATTENDED DELETION ACCEPTABLE.
# Every other destructive target in this repo is read by a person as it runs. This one is not,
# so it writes what it did where a person can read it afterwards, and the account it writes is
# the same one `make janitor` prints.

AGENT_LOG = "janitor.log"


def agent_label(root: str) -> str:
    """A label per CLONE, so two clones on one Mac do not evict each other's agent."""
    import hashlib
    return "com.pkmnscan.janitor." + hashlib.sha256(_real(root).encode()).hexdigest()[:8]


def agent_plist_path(root: str) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / (agent_label(root) + ".plist")


def install_agent(root: str, remove: bool, hour: int = 4) -> int:
    """Install or remove the daily unattended sweep. 0 when done, 1 when refused."""
    import plistlib

    label = agent_label(root)
    plist = agent_plist_path(root)

    if remove:
        if not plist.exists():
            say("no janitor agent installed for this checkout ({0}).".format(label))
            return 0
        run(["launchctl", "bootout", "gui/{0}/{1}".format(os.getuid(), label)])
        plist.unlink()
        say("janitor agent removed ({0}).".format(label))
        return 0

    main_tree = main_checkout(root)
    if not main_tree:
        return refuse("this clone's own layout is unreadable, so there is no tree to install "
                      "against.")
    if _real(root) != _real(main_tree):
        return refuse(
            "{0} is a linked worktree.".format(root),
            "",
            "A worktree is deleted routinely and its plist is an absolute path that would",
            "outlive it — launchd would retry a directory that is gone, forever, with",
            "nothing on screen to say so. Install this from the main checkout:",
            "",
            "  {0}".format(main_tree),
        )

    log = Path(main_tree) / ".serve" / AGENT_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": label,
        "ProgramArguments": [
            sys.executable, str(Path(__file__).resolve()),
            "--root", main_tree, "--confirm",
        ],
        "WorkingDirectory": main_tree,
        # A CALENDAR INTERVAL AND NEVER `KeepAlive`. This is a sweep that ends, not a service
        # that stays up — and launchd runs a missed calendar job at the next wake, so a Mac
        # asleep at the hour below still gets its sweep rather than skipping the day.
        "StartCalendarInterval": {"Hour": hour, "Minute": 0},
        "RunAtLoad": False,
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    }
    plist.parent.mkdir(parents=True, exist_ok=True)
    with open(plist, "wb") as handle:
        plistlib.dump(payload, handle)

    run(["launchctl", "bootout", "gui/{0}/{1}".format(os.getuid(), label)])
    loaded = run(["launchctl", "bootstrap", "gui/{0}".format(os.getuid()), str(plist)])
    say("janitor agent installed ({0}).".format(label))
    say("  plist     {0}".format(plist))
    say("  runs      daily at {0:02d}:00, and at the next wake if the Mac was asleep".format(hour))
    say("  receipt   {0}".format(log))
    say("  remove    make janitor-agent ARGS=--remove")
    if not loaded.ok:
        say("")
        say("  launchctl bootstrap failed: {0}".format(
            (loaded.err.splitlines() or ["(it said nothing)"])[-1]))
        say("  it will still load at your next login.")
        return 1
    return 0


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

    THE MAIN CHECKOUT IS NEVER TOUCHED, WHICH IS THE WHOLE OF D53 RESPECTED. `make up` there is
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
                        help="perform tier 2. Without this, tier 2 is a preview.")
    parser.add_argument("--install-agent", action="store_true",
                        help="install the daily unattended sweep as a launch agent. Main "
                             "checkout only. Add --remove to take it away.")
    parser.add_argument("--remove", action="store_true",
                        help="with --install-agent, remove it instead.")
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
    parser.add_argument("--stale-hours", type=float, default=STALE_HOURS,
                        help="how long a process a live session still owns may run before it is "
                             "worth a line. Never a reap, at any value. What "
                             "scripts/janitor-selftest.sh drives, so the threshold can be "
                             "proved to fire and to hold in one run.")
    parser.add_argument("--confine", default="",
                        help="only consider processes rooted under this path. What "
                             "scripts/janitor-selftest.sh drives, so a test signals its own "
                             "fixture and never a real process.")
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
    confine = _real(args.confine) if args.confine else ""

    if args.install_agent:
        return install_agent(root, args.remove)

    if args.branches:
        cut, kept = cut_merged_branches(root, args.confirm)
        if cut or kept:
            say("janitor: {0} branch(es) cut, {1} reported".format(cut, kept))
        return 0

    if args.tier1:
        reaped, reported, _ = sweep(root, sessions_dir, False, True, confine, args.stale_hours)
        if reaped or reported:
            say("janitor: {0} reaped, {1} reported".format(reaped, reported))
        return 0

    say("JANITOR — {0}{1}".format(root, "" if args.confirm else "  (PREVIEW)"))
    rule()
    reaped, reported, pending = sweep(
        root, sessions_dir, args.confirm, False, confine, args.stale_hours)
    rule()
    say("janitor: {0} reaped, {1} reported{2}".format(
        reaped, reported,
        "" if not pending else "  ({0} waiting on --confirm)".format(pending),
    ))
    # Only work waiting on a word is worth an exit code. Information is not a finding.
    return 1 if pending else 0


if __name__ == "__main__":
    sys.exit(main())
