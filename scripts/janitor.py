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

    scripts/janitor.py                     preview this repo. Presses nothing.
    scripts/janitor.py --confirm           reap tier 2 as well as tier 1.
    scripts/janitor.py --tier1             the provably-dead only, no prompt. What a hook runs.
    scripts/janitor.py --root PATH         another checkout. Repo-agnostic on purpose.
    scripts/janitor.py --teardown TREE     stop that tree's servers. What the hook runs.
    scripts/janitor.py --sessions DIR      read the liveness oracle elsewhere, for the self-test.
"""

from __future__ import annotations

import argparse
import contextlib
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


def live_sessions(sessions_dir: Path) -> List[Session]:
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
    if not sessions_dir.is_dir():
        return found
    for path in sorted(sessions_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pid = record.get("pid")
        cwd = record.get("cwd")
        if not isinstance(pid, int) or not isinstance(cwd, str) or not cwd:
            continue
        try:
            os.kill(pid, 0)
        except OSError:
            continue
        if not _same_process(record, pid):
            continue
        found.append(Session(pid, _real(cwd), str(record.get("name") or "")))
    return found


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


def dead_rooted_servers(mine: int, confine: str = "") -> List[Server]:
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
    for pid, command in _process_table():
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


def servers_under(tree: str, mine: int) -> List[Server]:
    """Anything running out of `tree` whose files are all still present.

    Reported, never reaped by this sweep: a tree that still exists may have a person in it, and
    stopping a server is `make down`'s job and the teardown hook's. The janitor's interest is
    only in saying that it is there.
    """
    root = _real(tree)
    found = []  # type: List[Server]
    for pid, command in _process_table():
        if pid == mine:
            continue
        for raw in _ABS_PATH_RE.findall(command):
            token = _real(raw)
            if token == root or token.startswith(root + os.sep):
                found.append(Server(pid, command, "", root))
                break
    return found


# -------------------------------------------------------------------------- the clone

class Tree(NamedTuple):
    path: str
    branch: str


def worktrees(root: str) -> List[Tree]:
    """Every registered working tree of this clone, main included."""
    got = run(["git", "worktree", "list", "--porcelain"], cwd=root)
    if not got.ok:
        return []
    trees = []  # type: List[Tree]
    here = ""
    for line in got.out.splitlines():
        if line.startswith("worktree "):
            here = _real(line[len("worktree "):].strip())
        elif line.startswith("branch ") and here:
            trees.append(Tree(here, line[len("branch refs/heads/"):].strip()))
            here = ""
        elif line.startswith("detached") and here:
            trees.append(Tree(here, ""))
            here = ""
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
        contents = {child.name for child in entry.iterdir()}
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


def sweep(root: str, sessions_dir: Path, confirm: bool, tier1: bool,
          confine: str = "") -> Tuple[int, int, int]:
    """(reaped, reported, pending). Prints the whole account as it goes.

    THE THIRD NUMBER IS THE ONLY ONE THAT SETS AN EXIT CODE, and the distinction is the point:
    `pending` is what a `--confirm` would act on, `reported` is everything worth a line. A kept
    `backup/` branch is a fact you should know and never a thing to do, so a healthy clone with
    one in it must not fail — the first build returned 1 there and made `make janitor` print
    `Error 1` on a repo with nothing wrong with it.
    """
    mine = os.getpid()
    sessions = live_sessions(sessions_dir)
    trees = worktrees(root)
    main_tree = main_checkout(root)
    held = {tree.branch for tree in trees if tree.branch}
    live_roots = {tree.path for tree in trees}

    reaped = reported = pending = 0

    # ---------------------------------------------------------------- tier 1: the dead
    orphans = dead_rooted_servers(mine, confine)
    for server in orphans:
        say("  reaped    pid {0} — its own {1} is gone".format(
            server.pid, Path(server.missing).name))
        say("            {0}".format(server.missing))
        # THE GROUP ONLY WHEN THIS PROCESS LEADS IT. A supervisor's children should go with it,
        # and `serve.py` spawns every one `start_new_session=True` so each IS its own leader —
        # but a process that is merely a member of somebody else's group would have that whole
        # group signalled on its behalf, which is a stranger's shell and everything in it.
        # Leader, group. Not leader, the pid alone.
        with contextlib.suppress(OSError):
            if os.getpgid(server.pid) == server.pid:
                os.killpg(server.pid, signal.SIGTERM)
            else:
                os.kill(server.pid, signal.SIGTERM)
        reaped += 1

    pruned = run(["git", "worktree", "prune", "-v"], cwd=root)
    for line in pruned.out.splitlines():
        if line.strip():
            say("  reaped    registration — {0}".format(line.strip()))
            reaped += 1

    # A husk is removed only once nothing is running under it — they regenerate otherwise.
    for husk in husks(root, live_roots):
        if servers_under(husk, mine):
            say("  KEPT      {0}".format(_relative(husk, root)))
            say("            a process is still running under it; it would come back")
            reported += 1
            continue
        shutil.rmtree(husk, ignore_errors=True)
        say("  reaped    {0}  (husk — no registration, no source)".format(_relative(husk, root)))
        reaped += 1

    if tier1:
        return reaped, reported, pending

    # ------------------------------------------------------- tier 2: needs a human word
    verb = "reaped   " if confirm else "would reap"
    for tree in trees:
        if tree.path == main_tree:
            continue
        who = sessions_in(sessions, tree.path)
        if who:
            say("  KEPT      {0}".format(_relative(tree.path, root)))
            say("            a session is live in it ({0})".format(
                ", ".join(s.name or str(s.pid) for s in who)))
            reported += 1
            continue
        dirty = run(["git", "status", "--porcelain"], cwd=tree.path)
        if dirty.ok and dirty.out:
            say("  KEPT      {0}".format(_relative(tree.path, root)))
            say("            {0} uncommitted file(s) — look at them yourself".format(
                len(dirty.out.splitlines())))
            reported += 1
            continue
        if servers_under(tree.path, mine):
            say("  KEPT      {0}".format(_relative(tree.path, root)))
            say("            a server is running out of it; stop it first")
            reported += 1
            continue
        say("  {0}  {1}  (no session, nothing uncommitted)".format(
            verb, _relative(tree.path, root)))
        pending += not confirm
        if confirm:
            gone = run(["git", "worktree", "remove", tree.path], cwd=root)
            if not gone.ok:
                tail = (gone.err.splitlines() or [""])[-1]
                say("            not removed — {0}".format(tail))
                reported += 1
                continue
            held.discard(tree.branch)
            reaped += 1
        else:
            reported += 1

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

    others = sessions_in(live_sessions(sessions_dir), tree)
    mine = os.getpid()
    others = [s for s in others if s.pid != mine]
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
    running = servers_under(tree, mine)
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
    parser.add_argument("--tier1", action="store_true",
                        help="the provably-dead only — no preview, no prompt. What a hook runs.")
    parser.add_argument("--sessions", default="",
                        help="where to read the liveness oracle. What scripts/janitor-selftest.sh "
                             "drives.")
    parser.add_argument("--teardown", metavar="TREE", default="",
                        help="stop what a leaving session started in TREE, and nothing else. "
                             "What the SessionEnd / WorktreeRemove hook runs.")
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

    if args.tier1:
        reaped, reported, _ = sweep(root, sessions_dir, False, True, confine)
        if reaped or reported:
            say("janitor: {0} reaped, {1} reported".format(reaped, reported))
        return 0

    say("JANITOR — {0}{1}".format(root, "" if args.confirm else "  (PREVIEW)"))
    rule()
    reaped, reported, pending = sweep(root, sessions_dir, args.confirm, False, confine)
    rule()
    say("janitor: {0} reaped, {1} reported{2}".format(
        reaped, reported,
        "" if not pending else "  ({0} waiting on --confirm)".format(pending),
    ))
    # Only work waiting on a word is worth an exit code. Information is not a finding.
    return 1 if pending else 0


if __name__ == "__main__":
    sys.exit(main())
