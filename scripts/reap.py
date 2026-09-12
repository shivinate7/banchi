#!/usr/bin/env python3
"""Kill what this session started, and refuse to kill anything else.

WHY THIS EXISTS. Twice in one session on 2026-09-09/10, a session cleaning up dev servers it
had itself launched killed a process belonging to somebody else:

  1. `pkill -f "capture_server.py"` — meant for a scratch server the session had started in a
     worktree. `pkill -f` matches on the WHOLE MACHINE, so it also matched
     `/Users/shivinate/Developer/pkmnscan/server/capture_server.py`: the owner's live capture
     server on :8000 over their real 1,625-card store, the process D53 exists to keep alive.
     The supervisor restored it 25s later and D88 meant the store survived, but any request in
     flight was severed mid-write.
  2. `for p in $(lsof -ti tcp:5439); do kill $p; done` — meant for the session's own Vite
     server. `lsof -ti tcp:PORT` returns every process HOLDING A SOCKET on that port, which
     includes CLIENTS: the second pid was the Claude desktop app's network-service helper.

Neither was a lapse of care. Both commands are the obvious spelling of the intent, and both
have a blast radius that is invisible in the text you type.

THREE SESSION NOTES ALREADY WARNED ABOUT THIS AND IT HAPPENED ANYWAY.
`pkill-f-is-machine-wide.md`, `dont-bounce-the-owners-servers.md` and
`a-pgrep-waiter-matches-itself.md` are all in this project's memory, all written after earlier
instances of the same class. A note that has to be remembered is not a guard — which is this
repo's standing preference everywhere else (D16, D17, D42, D111).

THE RULE THAT MAKES A MECHANICAL GUARD POSSIBLE, and the whole reason this is not a heuristic:
every process an agent session legitimately needs to kill was STARTED BY THAT SESSION and lives
under the checkout it is working in. Everything it must never kill lives somewhere else — the
main checkout's server, another worktree's servers, the desktop app, Chrome. So the question is
not "did you mean this?" but "does the target live under this checkout?", which has an answer.

The guard therefore does not pattern-match intent. It RESOLVES the command's actual targets —
running `pgrep` and `lsof` itself, read-only — and judges each pid. `pkill -f capture_server.py`
is allowed when the only match is yours and refused when it is not, which is the same command
being right on Monday and wrong on Tuesday. That is exactly the fact the text cannot carry.

    scripts/reap.py --hook            the PreToolUse hook on Bash. Reads the payload on stdin.
    scripts/reap.py                   preview everything running under this checkout.
    scripts/reap.py --confirm         stop it.
    scripts/reap.py port:5484 --confirm      whatever holds that port, if it is ours.
    scripts/reap.py match:vite --confirm     whatever `pgrep -f vite` finds, if it is ours.
    scripts/reap.py pid:12345 --confirm      that pid, if it is ours.
    scripts/reap.py --explain pid:12345      why one pid is or is not ours. Presses nothing.
    scripts/reap.py --root PATH       judge against another checkout. Repo-agnostic on purpose.

ONE FILE, TWO FACES, ONE PREDICATE. The hook and the reaper share `verdict_for`, and that is
the point rather than a convenience: a guard that refuses on one notion of "safe to kill" while
the tool it recommends uses another is a guard people learn to route around. `scripts/janitor.py`
already owns the neighbouring notion — what a FINISHED session left behind — and this file
deliberately does not duplicate it: the janitor sweeps trees, branches and orphans on its own
schedule, this decides one signal at the moment it is sent. What they share is the reasoning
(D53's server is untouchable, liveness is read and never guessed) and, where the shapes matched,
the code was copied with its argument rather than re-derived (`_real`, the process table, the
leader-only `killpg`).

IT IS REPO-AGNOSTIC AND IMPORTS NOTHING FROM THIS TREE, for `janitor.py`'s reason: `make
janitor-install` copies it to `~/.claude/bin` so a user-level hook covers every project on the
machine, and a copy that imported from this checkout would be broken everywhere else.

THE ESCAPE HATCH IS `PKMNSCAN_KILL=off` AND IT IS PRINTED IN EVERY REFUSAL, per the house rule
`PKMNSCAN_MAIN=off` set. A guard that is routinely bypassed is worse than none — CLAUDE.md says
as much about inline lint disables — so the hatch is sized to be reached for rarely: everything
provably yours is allowed without it, which is most of what a session ever wants to kill.

D18: this writes (it signals processes), so it is never on the commit path. Its SELF-TEST is,
and that self-test writes only under `mktemp -d` and signals only processes it spawned there.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

WIDTH = 76

# Every absolute path in a command line, as `ps -o command=` prints argv space-joined. A path
# containing a space cannot be recovered from that, which is why a miss here resolves to
# UNKNOWN — refused — rather than to a guess.
_ABS_PATH_RE = re.compile(r"(/[^\s]+)")

# The verdicts. Only OURS is ever signalled.
OURS = "ours"
OUTSIDE = "outside"
MAIN = "main"
UNKNOWN = "unknown"
GONE = "gone"


class Ran(NamedTuple):
    ok: bool
    out: str
    err: str


def run(args: Sequence[str], cwd: Optional[str] = None) -> Ran:
    """A subprocess, never a shell. Failure is a value here, not an exception."""
    try:
        done = subprocess.run(
            list(args), cwd=cwd, capture_output=True, text=True, check=False, timeout=10
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Ran(False, "", str(exc))
    return Ran(done.returncode == 0, done.stdout.strip(), done.stderr.strip())


def _real(path: str) -> str:
    """A path in the one spelling every comparison in this file uses.

    Copied from `scripts/janitor.py:_real` with its argument, because the trap is the same one:
    on this machine `/tmp` is `/private/tmp` and `/var` is `/private/var`, so `git` and `lsof`
    answer with the resolved spelling while a `cwd` and a `--root` carry whatever was typed.
    Comparing those as strings judges every target OUTSIDE its own checkout — which here would
    refuse a session every legitimate kill, and is precisely how a guard gets switched off.
    """
    try:
        return os.path.realpath(path)
    except OSError:
        return path


def _under(path: str, root: str) -> bool:
    return bool(root) and (path == root or path.startswith(root + os.sep))


# ------------------------------------------------------------------------- the two checkouts


# A directory that is not a WORKSPACE, and so may never be adopted as a root. Everything a
# person owns lives under one of these, so treating one as "this checkout" clears the whole
# machine in a single step — see `checkout_root` for the measurement that put this list here.
def _too_broad(path: str) -> bool:
    # ONE SET AND ONE TEST, deliberately. The first build had two arms — a fixed list, and a
    # separate check for the home directory and its ancestors — and every case the self-test
    # could pose was caught by EITHER, so removing one arm at a time changed nothing and two
    # mutation arms survived. Redundancy that no test can distinguish is not defence in depth;
    # it is code whose deletion nothing would notice.
    home = _real(str(Path.home()))
    broad = {home, "/", "/Users", "/home", "/tmp", "/private", "/private/tmp", "/private/var",
             "/var", "/usr", "/opt", "/Applications", "/System", "/Library"}
    broad.update(str(parent) for parent in Path(home).parents)   # `/Users`, `/home`, `/`
    return path in broad


def checkout_root(start: str) -> str:
    """The checkout `start` sits in — its git toplevel, or `start` itself when that is a
    workspace. EMPTY when there is no honest answer, and empty means nothing is ours.

    NOT `$PWD` FLAT. A session that runs a command from `app/` is standing in the same checkout
    as one standing at the top, and a server launched from the root would read as OUTSIDE for
    the first and OURS for the second. A guard whose answer depends on which subdirectory you
    happen to be in is a guard that is wrong half the time.

    AND THE FALLBACK MAY NOT BE A DIRECTORY THAT CONTAINS EVERYTHING, which is a hole this file
    shipped with and which only the USER-LEVEL install could expose. Inside a clone
    `git rev-parse` always answers, so the fallback never ran; the moment `make janitor-install`
    put this hook in the user's own `~/.claude/settings.json` it began firing in directories that
    are not repositories at all. **Measured from `/Users/shivinate` on 2026-09-10**: the fallback
    adopted the home directory as "this checkout", and `pgrep -f capture_server.py` — the exact
    command of incident 1 — resolved the owner's live `:8000` server to **OURS**, because
    `~/Developer/pkmnscan/server/capture_server.py` is under `~`.

    So a root has to be a place work is DONE, not a place work is KEPT. With no such root the
    answer is not a wider guess, it is that this file has nothing to reason with, and `_under`
    already reads an empty root as "nothing is under it" — every target is then refused and the
    hatch is printed, which is the direction every other unknown here resolves in.
    """
    got = run(["git", "rev-parse", "--show-toplevel"], cwd=start)
    if got.ok and got.out:
        return _real(got.out)
    here = _real(start)
    return "" if _too_broad(here) else here


def main_checkout(root: str) -> str:
    """The main working tree of this clone — the one whose `.git` is a directory.

    `janitor.py:main_checkout` verbatim. From a linked worktree this is a DIFFERENT directory,
    which is what makes incident 1 mechanically detectable rather than a matter of judgement.
    """
    got = run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=root)
    return _real(str(Path(got.out).parent)) if got.ok and got.out else ""


def linked_worktrees(root: str) -> List[str]:
    """This clone's LINKED worktrees — every working tree except the one `root` is.

    A LINKED WORKTREE LIVES INSIDE THE MAIN CHECKOUT ON THIS MACHINE, which makes it nested by
    path and separate by every rule this project has: D43 gives it its own store, its own
    `inventory/`, its own derived ports, and `checkout_root` called from inside one answers with
    the worktree rather than with main. So "under this checkout", asked from the main tree, must
    not mean "and everything in `.claude/worktrees/` too" — those are other sessions' checkouts,
    and their servers are other sessions' servers.

    Measured from the main checkout on 2026-09-12: a blanket sweep proposed to stop four
    processes, and ALL FOUR were worktrees' — two capture servers and a supervisor belonging to
    three other trees, one of them holding a live session. Two of the four were already reachable
    before the relative-path arm landed, so this is an older hole that the arm widens rather than
    opens; it is closed here because closing it is what keeps the widening safe.

    Empty from inside a linked worktree, which is correct and not a special case: `git worktree
    list` names every tree, and the only one excluded is `root` itself.
    """
    got = run(["git", "worktree", "list", "--porcelain"], cwd=root)
    if not got.ok:
        return []
    trees = [_real(line[len("worktree "):]) for line in got.out.splitlines()
             if line.startswith("worktree ")]
    return [tree for tree in trees if tree and tree != root and _under(tree, root)]


# ---------------------------------------------------------------------------- the processes


def process_table() -> List[Tuple[int, str]]:
    got = run(["ps", "-axww", "-o", "pid=,command="])
    if not got.ok:
        return []
    rows: List[Tuple[int, str]] = []
    for line in got.out.splitlines():
        head, _, command = line.strip().partition(" ")
        try:
            pid = int(head)
        except ValueError:
            continue
        if command.strip():
            rows.append((pid, command.strip()))
    return rows


def _commands_of(pids: Sequence[int]) -> Dict[int, str]:
    table = dict(process_table())
    return {pid: table.get(pid, "") for pid in pids}


def _parse_lsof_cwd(text: str) -> Dict[int, str]:
    """`lsof -Fpn` output as {pid: cwd}. One parser, because two callers ask `lsof` the same
    question over different pid sets and a second copy of this loop is a second thing to fix."""
    found: Dict[int, str] = {}
    pid: Optional[int] = None
    for line in text.splitlines():
        if line.startswith("p"):
            try:
                pid = int(line[1:])
            except ValueError:
                pid = None
        elif line.startswith("n") and pid is not None:
            found.setdefault(pid, _real(line[1:]))
    return found


def _cwds_of(pids: Sequence[int]) -> Dict[int, str]:
    """Each pid's working directory, for the pids `lsof` will answer about.

    A process launched by a relative path carries no absolute path in its argv at all — `npm`
    and `node` routinely do — so argv alone leaves those UNKNOWN and therefore refused, which
    would refuse a session the Vite server it started. The cwd is what rescues them.

    A pid `lsof` declines to answer about simply does not appear here, and the caller treats a
    pid with no evidence as UNKNOWN. Missing evidence is never read as absence of a problem.
    """
    if not pids:
        return {}
    got = run(["lsof", "-a", "-d", "cwd", "-p", ",".join(str(p) for p in pids), "-Fpn"])
    if not got.ok and not got.out:
        return {}
    return _parse_lsof_cwd(got.out)


def _all_cwds() -> Dict[int, str]:
    """Every process's working directory, in ONE call — 0.1s for 1,458 rows on the rig.

    The blanket sweep cannot name the pids it wants to ask about; that is what makes it the
    blanket sweep. So it reads the whole table and filters, exactly as `pids_under` already
    reads the whole process table and filters.

    An `lsof` that is absent or refuses answers with nothing, and the sweep then falls back to
    argv alone — the behaviour this file shipped with. Degrading is right here for the same
    reason a missing `lsof` leaves a pid UNKNOWN rather than OURS: less evidence never becomes
    more permission.
    """
    got = run(["lsof", "-a", "-d", "cwd", "-Fpn"])
    return _parse_lsof_cwd(got.out) if got.out else {}


def _descendants(roots: Set[int]) -> Set[int]:
    """`roots` and everything below them in the process tree.

    D53's supervisor RE-EXECS itself and replaces its children — twice inside twenty minutes on
    the day `janitor.py` was written — so a child can be running before the pidfile naming it
    has been rewritten. Walking down from the pids the pidfiles DO name closes that window
    without depending on the window being small.
    """
    if not roots:
        return set()
    got = run(["ps", "-axo", "pid=,ppid="])
    if not got.ok:
        return set(roots)
    parent: Dict[int, int] = {}
    for line in got.out.splitlines():
        bits = line.split()
        if len(bits) == 2:
            with contextlib.suppress(ValueError):
                parent[int(bits[0])] = int(bits[1])
    family = set(roots)
    for pid in parent:
        walk, seen = pid, 0
        while walk in parent and seen < 64:
            if walk in family:
                family.add(pid)
                break
            walk = parent[walk]
            seen += 1
    return family


def _ancestors(pid: int) -> Set[int]:
    """`pid` and everything above it in the process tree. `_descendants` pointed the other way.

    THE SWEEP MAY NOT SIGNAL THE SESSION THAT IS RUNNING IT. Once the blanket form places a
    process by its working directory, the session's own chain qualifies: measured in a worktree
    on 2026-09-12, five processes had a cwd under the checkout and THREE of them were the
    session — the Claude Code process, its launcher, and the shell the sweep was typed into.
    Signalling those stops the sweep, the turn and the session, which is a worse outcome than
    the leak this rule exists to close.

    It is the CHAIN and not the whole tree, deliberately. Excluding everything below the top
    ancestor would exclude the servers themselves: a `make server` backgrounded from a session's
    shell is a descendant of that session, and it is exactly what a sweep is for. The residue is
    a SIBLING shell — another tool call running concurrently in the same checkout — which this
    cannot tell from any other process working out of the tree. `make reap` previews by default,
    so that one is seen before it is signalled rather than discovered afterwards.
    """
    got = run(["ps", "-axo", "pid=,ppid="])
    if not got.ok:
        return {pid}
    parent: Dict[int, int] = {}
    for line in got.out.splitlines():
        bits = line.split()
        if len(bits) == 2:
            with contextlib.suppress(ValueError):
                parent[int(bits[0])] = int(bits[1])
    chain = {pid}
    walk, seen = pid, 0
    while walk in parent and seen < 64:
        walk = parent[walk]
        if walk <= 1 or walk in chain:
            break
        chain.add(walk)
        seen += 1
    return chain


def protected_pids(main: str) -> Set[int]:
    """The main checkout's supervisor, its children, and everything below them.

    THIS IS D53 WRITTEN AS A SET OF INTEGERS. `make launch-agent` keeps that process alive at
    login over the owner's real store; it is SUPPOSED to outlive every session, and a session
    standing in the main checkout would otherwise find it under its own root and judge it fair
    game. `scripts/serve.py` records the pid of each child it starts under `.serve/*.pid`, so
    the answer is on disk and does not have to be inferred from a command line.

    A pid here is refused even when it IS under this checkout, which is the one place this file
    overrules its own rule. The sanctioned way to stop that server is `make down ARGS=--confirm`,
    which drains rather than severing a write in flight — the refusal names it.
    """
    if not main:
        return set()
    roots: Set[int] = set()
    for marker in sorted((Path(main) / ".serve").glob("*.pid")):
        try:
            record = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pid = record.get("pid")
        if isinstance(pid, int):
            with contextlib.suppress(OSError):
                os.kill(pid, 0)
                roots.add(pid)
    return _descendants(roots)


# ------------------------------------------------------------------------------- the verdict


class Target(NamedTuple):
    pid: int
    verdict: str
    command: str
    where: str    # the path the verdict was reached on, or "" when there was none


def verdict_for(pids: Sequence[int], root: str, main: str) -> List[Target]:
    """The one predicate. Both faces of this file ask it and nothing else decides a signal.

    THE ORDER MATTERS AND THE DEFAULT IS REFUSAL. A protected pid loses before anything else is
    read; a pid with no readable evidence is UNKNOWN and therefore refused, never allowed on the
    strength of not having been disproved. `janitor.py:_same_process` takes the same direction
    for the same reason — a false refusal costs a session one extra sentence, a false permission
    costs the owner a process they were using.
    """
    guarded = protected_pids(main)
    live = [pid for pid in dict.fromkeys(pids) if pid > 0]
    commands = _commands_of(live)
    cwds = _cwds_of(live)
    out: List[Target] = []
    for pid in live:
        command = commands.get(pid, "")
        if pid in guarded:
            out.append(Target(pid, MAIN, command, main))
            continue
        if not command and pid not in cwds:
            # Gone between the resolve and now. There is nothing to judge and nothing left to
            # kill, and refusing a corpse would teach a session that the guard fires at random.
            # GONE is separated from UNKNOWN for exactly that reason: UNKNOWN is a live process
            # this file could not place, which is a refusal.
            out.append(Target(pid, GONE, "", ""))
            continue
        argv_paths = [_real(raw) for raw in _ABS_PATH_RE.findall(command)]
        here = cwds.get(pid, "")
        seen = argv_paths + ([here] if here else [])
        inside = next((path for path in seen if _under(path, root)), "")
        if inside:
            out.append(Target(pid, OURS, command, inside))
            continue
        if not seen:
            out.append(Target(pid, UNKNOWN, command, ""))
            continue
        # WHICH PATH THE REFUSAL QUOTES IS THE WHOLE VALUE OF THE REFUSAL. Every interpreted
        # process carries its INTERPRETER's absolute path first in argv — `/Library/.../Python`
        # — and quoting that says nothing about whose process it is. The main checkout beats
        # everything (it names D53 outright), then the cwd, then the LAST argv path, which for
        # `python3 /a/b/server.py` is the script rather than the interpreter.
        elsewhere = next((path for path in seen if _under(path, main)), "") if main else ""
        out.append(Target(pid, OUTSIDE, command,
                          elsewhere or here or (argv_paths[-1] if argv_paths else "")))
    return out


# -------------------------------------------------------------------- resolving what to kill


def pids_for_port(port: int) -> List[int]:
    """Everything holding a socket on `port` — LISTENERS AND CLIENTS ALIKE, which is the point.

    This is incident 2 in one function. `lsof -ti tcp:5439` is the obvious way to find "my dev
    server", and it is not what it returns: on 2026-09-10 the second pid was the Claude desktop
    app's network-service helper, which had merely connected to the page. The guard does not
    narrow this to listeners — narrowing would hide the very pid that needs judging. It resolves
    the same set the operator's command would have signalled, and refuses on the outsider.
    """
    got = run(["lsof", "-ti", "tcp:{0}".format(port)])
    return _ints(got.out)


def pids_for_pattern(pattern: str, full: bool = True) -> List[int]:
    got = run(["pgrep", "-f", pattern] if full else ["pgrep", pattern])
    return _ints(got.out)


def pids_for_name(name: str) -> List[int]:
    return _ints(run(["pgrep", "-x", name]).out)


def _ints(text: str) -> List[int]:
    found: List[int] = []
    for token in text.split():
        with contextlib.suppress(ValueError):
            found.append(int(token))
    return found


class Sweep(NamedTuple):
    pids: List[int]
    skipped: List[Tuple[int, str]]    # pid and why, printed rather than dropped in silence


def _placed_under(command: str, cwd: str, root: str) -> bool:
    """Does this process run code out of `root`? Two arms, and the second one is the fix.

    ARM ONE — an ABSOLUTE path in argv under the root. What this file shipped with, unchanged,
    and it stands on its own: a process can run this checkout's code from anywhere, and one
    whose script has since been DELETED still names it. Requiring existence would drop both.

    ARM TWO — a RELATIVE token in argv that, resolved against the process's own working
    directory, names an existing FILE under the root. This is the arm that was missing, and
    `make server` is the whole of why it is needed: the Makefile runs
    `$(PYTHON) server/capture_server.py`, `$(PYTHON)` is `.venv/bin/python`, and neither token
    is absolute — so the command line of a live capture server carries nothing under any
    checkout at all.

    "AN EXISTING FILE" IS THE WHOLE OF ARM TWO'S PRECISION, AND BOTH HALVES WERE MEASURED ON THE
    RIG'S OWN PROCESS TABLE ON 2026-09-12. `ps -o command=` prints argv space-joined, so a word
    is not a path just because it looks like one:

      * without EXISTENCE, the redirection inside a `zsh -c` script arrives as the word
        `2>/dev/null`, joins onto any working directory, and places every shell in the tree —
        it selected the Claude Code session itself and the sweep's own shell.
      * without FILE, the bare word `server` in `make server` resolves to the package DIRECTORY
        and places `make`, the shell around it, and anything else merely working in the tree.

    With both, the same table yields one process per real server and nothing else. A token is
    tried whether or not it holds a `/`, because a script run by its bare name in its own
    directory is as ordinary as one run by a path — and that is what the self-test's own subject
    is, so requiring a separator made the arm miss its own fixture.

    A FLAG IS NOT SKIPPED BY NAME, and that is not an oversight. An early build passed over any
    token starting with `-`; every mutation of that arm survived, because `<root>/-v` and
    `<root>/--shard=1/3` are not files and the test above already rejects them. This file's own
    `_too_broad` makes the ruling for cases like it: redundancy no test can distinguish is not
    defence in depth, it is code whose deletion nothing would notice.

    THE COST IS A DELETED SCRIPT, and arm one is why that is affordable: a process whose file has
    since been removed is still placed when its argv names it absolutely, and `scripts/janitor.py`
    owns the deleted-script class outright as its Tier 1.
    """
    for raw in _ABS_PATH_RE.findall(command):
        if _under(_real(raw), root):
            return True
    if not cwd:
        return False
    for token in command.split():
        if token.startswith("/"):
            continue
        joined = _real(os.path.join(cwd, token))
        if _under(joined, root) and os.path.isfile(joined):
            return True
    return False


def pids_under(root: str, mine: int) -> Sweep:
    """Everything running out of this checkout. `servers_under` in janitor.py, by pid.

    THE BLANKET FORM COULD NOT SEE A PROCESS LAUNCHED BY A RELATIVE PATH, AND THAT IS THE WHOLE
    DEFECT. `verdict_for` places a pid by an argv path under the root OR by a working directory
    under it, and says in as many words why the second arm is there — `npm` and `node` routinely
    carry no absolute path at all. This resolver read argv alone, so it could only ever offer the
    verdict the pids the verdict's FIRST arm would have caught, and every process the second arm
    exists for was invisible to the sweep.

    MEASURED IN A WORKTREE ON 2026-09-12, with a live capture server on that tree's own derived
    port: `make reap` resolved **0 processes** and printed `nothing to stop`, while
    `make reap ARGS=port:8235` resolved the same pid and judged it OURS. Three orphaned
    `capture_server.py` from three different trees were running on the machine at that moment,
    which is what the miss leaves behind. `make dev` was resolved throughout, because npm writes
    its argv absolutely — so the gap presented as "reap sees Vite and not Python", which reads
    like a carve-out and is not one.

    IT IS NOT D53'S CARVE-OUT, and that was established before anything here was changed.
    `protected_pids` globs `<main checkout>/.serve/*.pid` and nothing else; from a worktree it
    spares the main tree's supervisor and its children, correctly, and has nothing to say about
    a worktree's own server. The same measurement confirms it from both sides: the main
    checkout's live server judged MAIN, this worktree's judged OURS the moment it was named.

    AND THE SWEEP DOES NOT SIGNAL THE SESSION RUNNING IT. That hazard is older than this fix and
    reachable from the main checkout today: an agent's shell carries an absolute `cd` into the
    checkout in its own argv, so arm one already places it, and a bare `--confirm` would stop the
    shell the sweep was typed into. `_ancestors` is what keeps that from happening, and the
    skipped pids are printed rather than dropped in silence.
    """
    family = _ancestors(mine)
    nested = linked_worktrees(root)
    cwds = _all_cwds()
    found: List[int] = []
    skipped: List[Tuple[int, str]] = []
    for pid, command in process_table():
        if pid == mine:
            continue
        cwd = cwds.get(pid, "")
        if not _placed_under(command, cwd, root):
            continue
        if pid in family:
            skipped.append((pid, "this session's own chain"))
            continue
        tree = next((t for t in nested if _placed_under(command, cwd, t)), "")
        if tree:
            skipped.append((pid, "another checkout of this clone: {0}".format(tree)))
            continue
        found.append(pid)
    return Sweep(found, skipped)


# ------------------------------------------------------------------- reading a shell command

_KILL_WORDS = {"kill", "pkill", "killall"}

# Words that may stand in front of the real command word without changing what it is.
_PREFIXES = {
    "sudo", "command", "exec", "nohup", "time", "then", "do", "else", "elif", "builtin",
    "xargs", "env",
}

# A shell variable, a command substitution, a glob — anything whose value this file cannot know
# by reading the string. A kill argument matching this is the whole reason `unresolved` exists.
_OPAQUE = re.compile(r"[$`*?]")

# A job spec (`%1`, `%+`) and `$!` name a job of the SHELL THAT IS RUNNING THE COMMAND, which is
# the session's own one-shot shell. Whatever they refer to was started inside that same command,
# so they are provably the session's and are not a target this guard has anything to say about.
_OWN_JOB = re.compile(r"^(%[0-9%+-]*|\$!)$")

# `-0` sends no signal (a liveness probe) and `-l` lists signal names. Neither can kill anything,
# and refusing them would break the ordinary way a session waits for a process to exit.
_NO_SIGNAL = {"-0", "-l", "-L"}


class Intent(NamedTuple):
    kills: bool
    pids: List[int]
    unresolved: List[str]
    how: List[str]      # a sentence per resolved producer, for the refusal to quote


def _segments(command: str) -> List[List[str]]:
    """The command as a list of argv-ish word lists, one per shell segment.

    HEREDOC BODIES ARE CUT FIRST, and that is not fastidiousness. Writing a script that mentions
    `pkill` is an ordinary thing to do — this file was itself written through a heredoc — and a
    guard that reads a document being written as a command to be judged fires on the one class
    of command that can kill nothing at all. Everything from the first `<<` is dropped, which
    also drops a kill placed after the heredoc's terminator; that trade is deliberate and the
    cost is one extra line in a session's script.
    """
    head = command.split("<<", 1)[0]
    words: List[List[str]] = []
    for piece in re.split(r"[;\n&|(){}`]+|\$\(", head):
        piece = piece.strip()
        if not piece:
            continue
        try:
            argv = shlex.split(piece, comments=False)
        except ValueError:
            argv = piece.split()
        if argv:
            words.append(argv)
    return words


def _strip_prefixes(argv: List[str]) -> List[str]:
    out = list(argv)
    while out and (out[0] in _PREFIXES or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", out[0])):
        out.pop(0)
    return out


def _producers(segments: List[List[str]]) -> Tuple[List[int], List[str]]:
    """Every pid this command can name that this file can resolve by asking the system.

    A PRODUCER IS RESOLVED WHEREVER IT SITS IN THE COMMAND, not only where it is a kill's direct
    argument. `for p in $(lsof -ti tcp:5439); do kill $p; done` is the shape that cost incident 2,
    and in it the kill's argument is a loop variable that no amount of reading will resolve while
    the port is sitting in plain sight one clause away. So the question this asks is not "what is
    this kill's argument" but "what pids could this command be about", which the string does
    answer.
    """
    pids: List[int] = []
    how: List[str] = []
    for argv in segments:
        head = _strip_prefixes(argv)
        if not head:
            continue
        word, rest = head[0], head[1:]
        if word == "lsof" and any(flag.startswith("-t") for flag in rest):
            for token in rest:
                match = re.search(r"(?::|tcp:|udp:)(\d+)$", token)
                if match:
                    port = int(match.group(1))
                    found = pids_for_port(port)
                    pids.extend(found)
                    how.append("lsof on port {0} -> {1}".format(
                        port, ", ".join(str(p) for p in found) or "nothing"))
        elif word in ("pgrep", "pkill"):
            full = any(flag.startswith("-") and "f" in flag.lstrip("-") for flag in rest)
            pattern = next((token for token in reversed(rest) if not token.startswith("-")), "")
            if pattern and not _OPAQUE.search(pattern):
                found = pids_for_pattern(pattern, full)
                pids.extend(found)
                how.append("{0} {1} -> {2}".format(
                    "pgrep -f" if full else "pgrep", pattern,
                    ", ".join(str(p) for p in found) or "nothing"))
        elif word == "killall":
            for token in rest:
                if token.startswith("-") or _OPAQUE.search(token):
                    continue
                found = pids_for_name(token)
                pids.extend(found)
                how.append("killall {0} -> {1}".format(
                    token, ", ".join(str(p) for p in found) or "nothing"))
    return pids, how


def read_command(command: str) -> Intent:
    """What this command would signal, and what about it could not be read.

    THE DEFAULT IS "NOT A KILL". Most commands are not, and this returns as early as it can so
    that a hook on every Bash call costs nothing on the calls it has no opinion about.
    """
    if not any(word in command for word in _KILL_WORDS):
        return Intent(False, [], [], [])

    segments = _segments(command)
    kills = False
    opaque: List[str] = []
    literals: List[int] = []

    for argv in segments:
        head = _strip_prefixes(argv)
        if not head or head[0] not in _KILL_WORDS:
            continue
        rest = head[1:]
        if head[0] == "kill":
            if any(flag in _NO_SIGNAL for flag in rest):
                continue          # a probe, not a signal
            kills = True
            skip = False
            for token in rest:
                if skip:
                    skip = False
                    continue
                if token == "-s" or token == "-n":
                    skip = True
                    continue
                if token == "--" or re.match(r"^-\w+$", token):
                    continue
                if _OWN_JOB.match(token):
                    continue      # this shell's own job — provably the session's
                if re.match(r"^\d+$", token):
                    literals.append(int(token))
                    continue
                opaque.append(token)
        else:
            kills = True
            pattern = next((token for token in reversed(rest) if not token.startswith("-")), "")
            if not pattern or _OPAQUE.search(pattern):
                opaque.append(pattern or head[0])

    if not kills:
        return Intent(False, [], [], [])

    resolved, how = _producers(segments)
    pids = list(dict.fromkeys(literals + resolved))

    # AN OPAQUE ARGUMENT IS FORGIVEN ONLY WHEN THE COMMAND ANSWERS IT ELSEWHERE. `kill $p` with a
    # producer one clause away is the loop shape and is judged on the producer; `kill $p` alone
    # is a command whose blast radius is genuinely unreadable, and that is refused rather than
    # guessed at. The residual is a command that resolves one set and kills a different one,
    # which no reading of a string can catch and which no session has ever written by accident.
    unresolved = [] if resolved else opaque
    return Intent(True, pids, unresolved, how)


# ------------------------------------------------------------------------------ the refusals

_REFUSED = {
    MAIN: "the main checkout's own server (D53) — it is the owner's product, kept alive at "
          "login, over their real store",
    OUTSIDE: "outside this checkout",
    UNKNOWN: "not placeable — no absolute path in its argv and no readable cwd",
}


def _short(command: str, width: int = 96) -> str:
    """A long command line, ELIDED IN THE MIDDLE rather than at the end.

    Trimming the tail is the obvious spelling and it hides the only informative part: every
    interpreted process starts with its interpreter's long absolute path, so
    `python3 /Library/…/Python3.framework/…/Python /a/b/listen.py` truncates to the framework
    and never reaches `listen.py`. The refusal exists to tell you WHICH process it means.
    """
    if len(command) <= width:
        return command
    head = (width - 3) // 3
    return command[:head] + "…" + command[-(width - 3 - head):]


def hook(payload: dict) -> int:
    """The PreToolUse hook on Bash. Exit 2 blocks the call and hands stderr back to the session.

    IT FAILS OPEN ON ITS OWN BUGS, which is `guard-opsec.sh`'s hard-won rule and is not
    negotiable here either: a guard that blocks every shell command when `lsof` is missing or
    its own parser throws is a guard somebody switches off inside a day, and a switched-off
    guard protects nothing. Note the asymmetry, because it is the design: a broken GUARD fails
    open, an unreadable TARGET fails closed. The first is this file being wrong about itself,
    the second is this file being right that it does not know.
    """
    command = str(payload.get("tool_input", {}).get("command", "") or "")
    if not command:
        return 0
    if os.environ.get("PKMNSCAN_KILL") == "off" or "PKMNSCAN_KILL=off" in command:
        return 0

    intent = read_command(command)
    if not intent.kills:
        return 0

    root = checkout_root(os.getcwd())
    main = main_checkout(root)
    targets = verdict_for(intent.pids, root, main)
    bad = [t for t in targets if t.verdict in (MAIN, OUTSIDE, UNKNOWN)]
    if not bad and not intent.unresolved:
        return 0

    lines = ["BLOCKED: this would signal a process this session did not start."]
    for target in bad:
        lines.append("  pid {0} — {1}".format(target.pid, _REFUSED[target.verdict]))
        if target.command:
            lines.append("      {0}".format(_short(target.command)))
        if target.where:
            lines.append("      {0}".format(target.where))
    for token in intent.unresolved:
        lines.append("  `{0}` — this guard cannot tell what pid that names, so it cannot tell "
                     "whose it is.".format(token))
    for note in intent.how:
        lines.append("  resolved: {0}".format(note))
    lines.append("")
    if root:
        lines.append("  Everything an agent session may kill was started BY that session and "
                     "lives under")
        lines.append("  {0}. What is refused above does not.".format(root))
    else:
        # `checkout_root` returned nothing, so this is not a workspace — a home directory, `/`,
        # or somewhere else that contains everything. There is no checkout to be inside of, so
        # nothing here can be shown to be this session's.
        lines.append("  {0} is not a workspace — it contains everything, so nothing in it can "
                     "be".format(os.getcwd()))
        lines.append("  shown to be this session's. Run this from the checkout whose process it "
                     "is.")
    lines.append("")
    lines.append("  Use the reaper, which signals only what is under this checkout and says "
                 "what it")
    lines.append("  refused:   make reap                     preview")
    lines.append("             make reap ARGS=--confirm      stop it")
    lines.append("             make reap ARGS=\"port:5484 --confirm\"")
    if any(t.verdict == MAIN for t in targets):
        lines.append("")
        lines.append("  To stop the MAIN checkout's server on purpose, drain it rather than "
                     "severing a")
        lines.append("  write in flight:  make down ARGS=--confirm   (in that checkout)")
    lines.append("")
    lines.append("  PKMNSCAN_KILL=off runs the command anyway.")
    print("\n".join(lines), file=sys.stderr)
    return 2


# -------------------------------------------------------------------------------- the reaper


def _targets_from_args(specs: Sequence[str], root: str, mine: int) -> Tuple[List[int], List[str]]:
    pids: List[int] = []
    how: List[str] = []
    for spec in specs:
        kind, _, value = spec.partition(":")
        if not value:
            kind, value = "match", spec
        if kind == "pid":
            pids.extend(_ints(value))
            how.append("pid {0}".format(value))
        elif kind == "port":
            found = pids_for_port(int(value)) if value.isdigit() else []
            pids.extend(found)
            how.append("port {0} -> {1} process(es)".format(value, len(found)))
        elif kind == "match":
            found = pids_for_pattern(value)
            pids.extend(found)
            how.append("pgrep -f {0} -> {1} process(es)".format(value, len(found)))
        else:
            how.append("unknown target `{0}` — use pid:, port: or match:".format(spec))
    if not specs:
        sweep = pids_under(root, mine)
        pids = sweep.pids
        how.append("everything running under this checkout -> {0} process(es)".format(len(pids)))
        # SAY WHAT IS BEING PASSED OVER. A sweep that silently omits something is the defect
        # this resolver had, one register up: each of these is skipped for a real reason, and a
        # reader who is not told cannot tell a reason from the process not having been seen.
        for reason in sorted({why for _, why in sweep.skipped}):
            these = sorted(pid for pid, why in sweep.skipped if why == reason)
            how.append("skipped {0} — {1}: {2}".format(
                len(these), reason, ", ".join(str(p) for p in these)))
    return pids, how


def reap(specs: Sequence[str], root: str, main: str, confirm: bool) -> int:
    """Signal what is ours; report, in full, what is not.

    THE REFUSALS ARE PRINTED RATHER THAN SWALLOWED, and that is the difference between this and
    a `pkill` that quietly does the right thing on a good day. A session that asked for a port
    and got one kill and one refusal has learned the thing the incident had to teach.
    """
    mine = os.getpid()
    pids, how = _targets_from_args(specs, root, mine)
    pids = [pid for pid in dict.fromkeys(pids) if pid != mine]
    targets = verdict_for(pids, root, main)

    print("reap — this checkout is {0}".format(
        root or "NOWHERE: {0} is not a workspace, so nothing here is ours".format(os.getcwd())))
    for note in how:
        print("  resolved: {0}".format(note))
    print("")

    ours = [t for t in targets if t.verdict == OURS]
    refused = [t for t in targets if t.verdict in (MAIN, OUTSIDE, UNKNOWN)]
    for target in ours:
        print("  {0}  pid {1}  {2}".format(
            "stopped   " if confirm else "would stop", target.pid, _short(target.command)))
        print("              {0}".format(target.where))
        if confirm:
            # THE GROUP ONLY WHEN THIS PROCESS LEADS IT — `janitor.py`'s rule, and its argument
            # applies unchanged: a supervisor's children should go with it, and `serve.py`
            # starts every one `start_new_session=True` so each IS its own leader; a process
            # that is merely a MEMBER of somebody else's group would have that whole group
            # signalled on its behalf, which is a stranger's shell and everything in it.
            with contextlib.suppress(OSError):
                if os.getpgid(target.pid) == target.pid:
                    os.killpg(target.pid, signal.SIGTERM)
                else:
                    os.kill(target.pid, signal.SIGTERM)
    for target in refused:
        print("  REFUSED     pid {0}  {1}".format(target.pid, _short(target.command)))
        print("              {0}".format(_REFUSED[target.verdict]))
        if target.where:
            print("              {0}".format(target.where))
    if not ours and not refused:
        print("  nothing to stop.")
    print("")
    if ours and not confirm:
        print("  --confirm to stop the {0} above.".format(len(ours)))
        return 1
    return 0


def explain(specs: Sequence[str], root: str, main: str) -> int:
    mine = os.getpid()
    pids, _ = _targets_from_args(specs, root, mine)
    for target in verdict_for(pids, root, main):
        print("pid {0}  {1}".format(target.pid, target.verdict.upper()))
        print("  {0}".format(_short(target.command) or "(gone)"))
        print("  {0}".format(target.where or "no path this file could place"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reap",
        description="Stop what this session started, and refuse to stop anything else.",
    )
    parser.add_argument("targets", nargs="*", metavar="TARGET",
                        help="pid:N, port:N or match:SUBSTRING. Omit for everything running "
                             "under this checkout.")
    parser.add_argument("--confirm", action="store_true",
                        help="actually signal. Without it this previews and presses nothing.")
    parser.add_argument("--explain", action="store_true",
                        help="say why each target is or is not ours. Presses nothing.")
    parser.add_argument("--hook", action="store_true",
                        help="read a PreToolUse payload on stdin and judge its command.")
    parser.add_argument("--root", default="",
                        help="judge against this checkout instead of the current directory.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.hook:
        try:
            payload = json.load(sys.stdin)
            if not isinstance(payload, dict):
                return 0
            return hook(payload)
        except Exception:      # noqa: BLE001 — the header's rule: a broken guard fails open.
            return 0
    root = _real(args.root) if args.root else checkout_root(os.getcwd())
    main_tree = main_checkout(root)
    if args.explain:
        return explain(args.targets, root, main_tree)
    return reap(args.targets, root, main_tree, args.confirm)


if __name__ == "__main__":
    sys.exit(main())
