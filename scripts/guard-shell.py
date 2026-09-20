#!/usr/bin/env python3
"""Refuse nine shell mistakes this repo has already made and paid for.

EVERY CLAUSE HERE HAS AN INCIDENT BEHIND IT, and not one of them was a lapse of care: each
was a rule somebody had already written down, in a memory file or in CLAUDE.md, and then
broken by a session that had read it. That is not a reason to write the rule again; it is
what D171 rules a rule IS. A rule is read once, at the start, and then competes with the
work. So these nine are mechanical.

    1. `git checkout <path>` / `git restore <path>` over a file with uncommitted changes
       2026-09-06: three mutation cases used `sed -i.bak` and the fourth used
       `git checkout cli/cmd_reprice.py`. Nothing was committed, so it reverted to HEAD and
       destroyed ~240 lines of that session's work. "Every other file survived, which made it
       look at first like a smaller problem than it was."

    2. A write outside the checkout this session is standing in
       2026-09-06: an absolute-path `cd` prefix wrote ~1,500 lines into the owner's MAIN
       checkout, on `main`, for most of a session — and `make launch-agent`'s supervisor
       hot-reloaded that uncommitted branch code into their live `:8000` capture server
       repeatedly while they were using the app over their real store.

    3. `gh api -f k=v` with no method
       2026-09-12: a field implies a BODY, so gh sends POST. The call hung past a 120s tool
       timeout and left a background process to reap, "which reads as a network problem
       rather than as a malformed request."

    4. `ln -s` at a path that already exists
       2026-08-29: `ln -s <main>/harness/images harness/images` over an existing directory
       made `harness/images/images` instead of failing. A copy brought the loop back,
       `Path.mkdir(exist_ok=True)` raised FileExistsError, T1 died naming only the symptom,
       and iCloud renamed the real 133 MB directory — the largest thing in this tree with no
       backup anywhere — to `images 2`, empty.

    5. A polling loop
       2026-09-12, twice. A session that had read the rule four days earlier wrote
       `until ! pgrep -f 'scratchpad/drive.sh'`, whose `pgrep -f` matched the loop's own
       command line, so the condition was never false and the work chained after it never
       ran. The same day a backgrounded `while`/`sleep` merge driver ran 119 rounds over
       3h58m — across a compaction — racing the session's own merges. Nothing in this repo
       could see it: `make janitor` reads a live process as live, and `make reap` acts only
       when asked. A human noticed it in their UI.

    6. `git push <remote> HEAD` (or `<remote> <the-branch's-own-name>`) when the branch
       tracks a DIFFERENT name upstream
       2026-09-12: a coordinator resolving a merge conflict stood on a local branch a
       background agent had named `pr-h-readings-table-local`, whose configured upstream was
       actually `origin/claude/pr-h-readings-table` — the agent had pushed its squashed
       commit to the real PR branch under a name that did not match the local one. `git push
       origin HEAD` reported success, `[new branch] HEAD -> pr-h-readings-table-local`, and
       had created a stray branch on origin without touching the PR branch at all. Git's own
       `push.default=simple` refuses exactly this shape for a BARE `git push` and even prints
       the fix — but naming a refspec, even an unqualified `HEAD`, is git's own signal that
       the caller knows what they want, and that signal was wrong.

    7. `git stash pop` / `drop` / `clear`, or a bare `git stash`, in a clone with ~30
       working trees sharing one stash stack
       No single incident is behind this one — the owner's OWN parent CLAUDE.md names the
       command outright before this repo ever mistyped it: "Never run `git stash` … in a
       shared checkout." D173 is what a rule with no incident yet still gets: mechanised
       now, on the strength of the argument alone, rather than waited on until it is paid
       for. The argument: a stack entry made by another worktree's session is
       indistinguishable, by index, from this session's own — `stash@{0}` names "whatever is
       on top right now", not "the thing I pushed a minute ago" — so `pop`/`drop`/`clear`
       consume or destroy an entry the caller never identified, and a bare `git stash` is the
       same command habit uses interchangeably to mean "save" AND "restore".

    8. `git reset --hard` / `--merge` / `--keep` over a working tree that still holds
       uncommitted changes
       Also named outright by the parent CLAUDE.md, and mechanised for D173's reason above
       rather than after a loss. A hard-family reset overwrites the index and the working
       tree from a commit with no confirmation and no record of what it overwrote — the same
       "reverts to HEAD, silently, without asking" shape rank 1's `git checkout` already
       covers for a single path, one level up: the whole tree instead of one file.

    9. A command that waits for minutes and NARRATES while it does, piped into `tail` or
       redirected away
       2026-09-20. `make merge` pushes a claim commit and waits for that commit's checks;
       `check.yml` takes four to five minutes, measured across 12 consecutive runs the same
       day, and the wait prints a line a minute saying what it is waiting on. Sessions
       habitually type `… 2>&1 | tail -18`, which block-buffers that heartbeat and then keeps
       only the end of it, so five to twenty minutes of correct waiting is indistinguishable
       from a hang. One session did it twice in an evening while knowing better, and other
       sessions reached the same wrong conclusion about the same working merge. The parent
       rule "never discard a command's output" already covers this in spirit — but a pipe to
       `tail` does not READ as discarding, which is why the rule alone stopped nobody.
       THIS ONE CLAUSE DOES NOT RESOLVE ITS SUBJECT FROM THE SYSTEM and says so in its own
       section: whether a command blocks and narrates is not a question the filesystem or the
       process table can answer in advance, so the roster is named, short, per-incident, and
       reconciled by the self-test against the heartbeat constant in the file that runs it.

THE STANDARD IS `scripts/reap.py:hook`'S AND IT IS NOT NEGOTIABLE HERE EITHER:

    a broken GUARD fails OPEN — any parse error, any bug here, an unreadable payload, a
                                missing `git`: exit 0 and refuse nothing
    an unreadable TARGET fails CLOSED — but only where "unreadable" is this file being right
                                that it does not know AND the harm is unrecoverable, which is
                                true of none of these nine: each of the first eight RESOLVES
                                its subject and the ninth names a roster of two, and a subject
                                a clause cannot resolve is a command it has no opinion about

RESOLUTION, NEVER SPELLING, wherever the question has a real answer. `git checkout main` and
`git checkout CLAUDE.md` are the same six characters of verb: the first is a branch and the
second destroys work, and only the filesystem and `git status` can say which. `ln -s a b` is
right on Monday and wrong on Tuesday depending on whether `b` exists. `git push origin HEAD`
is right when the upstream is named the same and wrong when it is not, and only
`branch.<name>.merge` can say which. That is reap.py's whole argument, applied to five more
commands — and clause 9, which cannot be resolved that way, argues its own roster instead of
pretending otherwise.

FALSE POSITIVES ARE THE ONLY WAY A GUARD LIKE THIS DIES, and it dies silently — the hatch
goes into a shell profile and nobody ever sees the refusal again. So every clause is narrow on
purpose, every legitimate shape this repo actually types is pinned as PASSING in
`scripts/guard-shell-selftest.sh`, and each is RUN there before it is scored, because a case
that is secretly a typo passes for the wrong reason.

NINE CLAUSES, NINE HATCHES, AND THAT IS DELIBERATE. One switch for the whole hook would mean
disarming the destructive-checkout clause in order to make a symlink, which is how a guard
stops being one. Each refusal prints only its own, each is honoured in the environment and
inline, and all nine are documented in CLAUDE.md (`make docs-audit`'s `env names` row refuses
a variable the code reads and no markdown names).

    scripts/guard-shell.py --hook            the PreToolUse hook. Payload on stdin.
    scripts/guard-shell.py --explain CMD     the verdict for one command. Presses nothing.
    scripts/guard-shell.py --explain-write PATH   the verdict for one write target.

D18: this writes nothing and signals nothing, so it could gate a commit — but it is a hook
rather than a check, and its SELF-TEST is what `make check` runs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, NamedTuple, Optional, Sequence, Set, Tuple

# THE PARSER IS SHARED WITH `scripts/silent-write-guard.py`, and the import is guarded because
# a guard that cannot load its parser has no opinion rather than an objection. Without this
# the module would raise at import time, and an exit code that is neither 0 nor 2 is a
# harness-defined behaviour this file should not be relying on.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import shell_parse
except Exception:                                             # noqa: BLE001 — fail open
    shell_parse = None                                        # type: ignore[assignment]


# ----------------------------------------------------------------------------- the clauses
#
# DECLARED, because six clauses each with their own hatch is six names a reader has to be
# able to find. The selftest reads this table so a clause added without a hatch, or a hatch
# named in one place and printed in another, is a failing case rather than a silent hole.

class Clause(NamedTuple):
    name: str
    hatch: str
    rule: str


CLAUSES = (
    Clause("checkout", "PKMNSCAN_CHECKOUT",
           "never `git checkout <path>` or `git restore <path>` over a modified file"),
    Clause("tree", "PKMNSCAN_TREE",
           "never write outside the checkout this session is standing in, and never `cd` "
           "into another one"),
    Clause("gh", "PKMNSCAN_GH",
           "never pass -f/-F to `gh api` without naming the method"),
    Clause("link", "PKMNSCAN_LINK",
           "use `ln -sfn`, or test the path is absent, when linking"),
    Clause("wait", "PKMNSCAN_WAIT",
           "never poll in a loop — background the work and take its notification"),
    Clause("push", "PKMNSCAN_PUSH",
           "never `git push <remote> HEAD` / `<remote> <branch>` when the tracked upstream "
           "is a different, non-default branch"),
    Clause("stash", "PKMNSCAN_STASH",
           "never a bare `git stash`, `git stash pop`, or `git stash drop`/`clear` with no "
           "explicit entry — the stack is shared across every worktree"),
    Clause("reset", "PKMNSCAN_RESET",
           "never `git reset --hard`/`--merge`/`--keep` over a tree that still holds "
           "uncommitted tracked changes"),
    Clause("narrate", "PKMNSCAN_NARRATE",
           "never hide the heartbeat of a command that waits for minutes — let its output "
           "reach the session as it happens"),
)

HATCH = {clause.name: clause.hatch for clause in CLAUSES}


class Refusal(NamedTuple):
    clause: str
    lines: List[str]        # the body; the heading and the hatch are added by `render`
    heading: str


class Verdict(NamedTuple):
    refusals: List[Refusal]
    notes: List[str]        # printed, exit 0 — what this file looked at and could not read


def _off(clause: str, command: str) -> bool:
    """Whether this clause's hatch is set, in either of `PKMNSCAN_KILL`'s two forms."""
    name = HATCH[clause]
    return os.environ.get(name) == "off" or (name + "=off") in command


# ------------------------------------------------------------------------------- the system

def _run(args: Sequence[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
    """A subprocess, never a shell. Failure is a value here, not an exception.

    `reap.py:run`'s shape. Read-only by construction: every caller below passes a `git`
    query, and a guard that wrote anything would be a guard on the commit path (D18).
    """
    try:
        done = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True,
                              check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False, ""
    return done.returncode == 0, done.stdout


def _real(path: str) -> str:
    """A path in the one spelling every comparison here uses.

    `reap.py:_real` verbatim, for its reason: on this machine `/tmp` is `/private/tmp` and
    `/var` is `/private/var`, so git and the filesystem answer with the resolved spelling
    while a cwd carries whatever was typed. Comparing those as strings judges every target
    OUTSIDE its own checkout, which is precisely how a guard gets switched off.
    """
    try:
        return os.path.realpath(path)
    except OSError:
        return path


def _under(path: str, root: str) -> bool:
    return bool(root) and (path == root or path.startswith(root + os.sep))


def _too_broad(path: str) -> bool:
    """A directory that is not a WORKSPACE, and so may never be adopted as a root.

    `reap.py:_too_broad`, and its measurement is the reason it is copied rather than
    simplified: from `/Users/shivinate` the fallback adopted the HOME directory as "this
    checkout", which would make every path on the machine `_under` the root and this file's
    second clause vacuous.
    """
    home = _real(str(Path.home()))
    broad = {home, "/", "/Users", "/home", "/tmp", "/private", "/private/tmp", "/private/var",
             "/var", "/usr", "/opt", "/Applications", "/System", "/Library"}
    broad.update(str(parent) for parent in Path(home).parents)
    return path in broad


def checkout_root(start: str) -> str:
    """The checkout `start` sits in — its git toplevel, or `start` when that is a workspace.

    EMPTY when there is no honest answer, and empty means this file cannot place anything.
    `reap.py:checkout_root`'s contract, with the one difference that matters here: an empty
    root makes the `tree` clause ALLOW and say so, where reap.py's makes it refuse. The
    asymmetry is the harm — a signal sent to a stranger's process cannot be taken back, and a
    file written in a directory that is not a checkout is a file somebody can move.
    """
    ok, out = _run(["git", "rev-parse", "--show-toplevel"], cwd=start)
    if ok and out.strip():
        return _real(out.strip())
    here = _real(start)
    return "" if _too_broad(here) else here


def _temp_roots() -> List[str]:
    """Where a throwaway file legitimately goes, resolved.

    `mktemp -d` is how every self-test in this repo works and where a session's scratchpad
    lives, so these are not an exemption so much as the other half of the rule: a temp
    directory belongs to no checkout, which is the whole reason it is used.
    """
    roots = ["/tmp", "/private/tmp", "/var/folders", "/private/var/folders"]
    for name in ("TMPDIR", "TMP", "TEMP"):
        value = os.environ.get(name)
        if value:
            roots.append(value)
    roots.append(tempfile.gettempdir())
    return [_real(root).rstrip(os.sep) or "/" for root in roots]


def _repo_holding(target: str) -> str:
    """The checkout a path lives in, asked of git at its nearest existing parent, or `""`."""
    directory = os.path.dirname(target)
    for _ in range(24):
        if os.path.isdir(directory):
            ok, out = _run(["git", "rev-parse", "--show-toplevel"], cwd=directory)
            return _real(out.strip()) if ok and out.strip() else ""
        parent = os.path.dirname(directory)
        if parent == directory:
            return ""
        directory = parent
    return ""


def _sanctioned_outside(target: str) -> str:
    """Why a path outside this checkout is nevertheless a legitimate write, or `""`.

    THE USER'S OWN `~/.claude` IS NOT THIS CHECKOUT AND IS NOT A MISTAKE: memory files live
    there, `make janitor-install` deliberately copies two scripts into it, and user-level
    settings are the point of it.

    A TEMP DIRECTORY IS SANCTIONED ONLY WHILE IT IS NOT ITSELF A CHECKOUT, and that
    qualification is load-bearing twice over. Every self-test in this repo builds its fixture
    with `mktemp -d` and `git init` — including this guard's own — so a flat temp exemption
    would make the fixture for THIS clause unable to pose its case, which is D157's rule
    about a fixture that collides with a machine-wide subject arriving one register up. And
    it is the honest reading anyway: what makes a scratch file safe is that it belongs to no
    checkout, not the directory it happens to sit in.
    """
    if _under(target, "/dev"):
        return "a device, which is not a file in any checkout"
    dot_claude = _real(str(Path.home() / ".claude"))
    if _under(target, dot_claude):
        return "the user's own ~/.claude — memory, settings, and `make janitor-install`'s copies"
    for root in _temp_roots():
        if _under(target, root):
            holder = _repo_holding(target)
            if not holder:
                return "a temporary directory, which belongs to no checkout"
            return ""
    return ""


# ------------------------------------------------------------- 1. the destructive checkout

_RESTORE_VERBS = {"checkout", "restore"}

# Flags that consume the next word. `-b`/`-B`/`--orphan` are handled separately because they
# make the whole invocation a branch creation, which can never discard a working file.
_CHECKOUT_VALUE_FLAGS = {"--conflict", "--pathspec-from-file", "-t", "--track"}
_RESTORE_VALUE_FLAGS = {"-s", "--source", "--conflict", "--pathspec-from-file"}
_BRANCH_MAKERS = {"-b", "-B", "--orphan"}


class Restoring(NamedTuple):
    """What a `git checkout` / `git restore` invocation would do to the working tree."""
    paths: List[str]              # operands this file reads as pathspecs
    source_named: str             # a tree-ish the caller named, or ""
    passes: str                   # non-empty when nothing can be discarded, and why
    unresolved: List[str]         # operands that are neither a path nor a ref


def _flag_value(token: str, flags: Set[str]) -> bool:
    return token in flags or any(token.startswith(flag + "=") for flag in flags)


def _read_restore(verb: str, rest: Sequence[str], cwd: str) -> Restoring:
    """The operands of a checkout/restore, classified by asking git and the filesystem.

    THE DISCRIMINATOR IS RESOLUTION AND NEVER SPELLING, which is the only way `git checkout
    main` and `git checkout CLAUDE.md` can be told apart. A token that resolves to neither a
    path on disk nor a commit is reported and ALLOWED: this file not knowing is not evidence
    the command is wrong.
    """
    value_flags = _RESTORE_VALUE_FLAGS if verb == "restore" else _CHECKOUT_VALUE_FLAGS
    operands: List[str] = []
    after_dashes: List[str] = []
    source = ""
    staged = worktree = False
    index = 0
    seen_dashes = False
    while index < len(rest):
        token = rest[index]
        index += 1
        if seen_dashes:
            after_dashes.append(token)
            continue
        if token == "--":
            seen_dashes = True
            continue
        if token in _BRANCH_MAKERS or _flag_value(token, _BRANCH_MAKERS):
            return Restoring([], "", "it creates a branch, so no working file is restored", [])
        if token in ("-p", "--patch"):
            return Restoring([], "", "`--patch` asks about every hunk before it discards one", [])
        if token in ("-S", "--staged"):
            staged = True
            continue
        if token in ("-W", "--worktree"):
            worktree = True
            continue
        if token in ("-s", "--source") and index < len(rest):
            source = rest[index]
            index += 1
            continue
        if token.startswith("--source="):
            source = token.split("=", 1)[1]
            continue
        if _flag_value(token, value_flags):
            if "=" not in token and index < len(rest):
                index += 1
            continue
        if token.startswith("-"):
            continue
        operands.append(token)

    if staged and not worktree:
        return Restoring([], source,
                         "`--staged` alone rewrites the index and leaves the file on disk", [])

    if seen_dashes:
        paths = after_dashes
        if operands and not source:
            source = operands[0]
    elif verb == "restore":
        paths = operands
    elif len(operands) > 1:
        # `git checkout <tree-ish> <path>...` — git's own reading with no `--`.
        source, paths = operands[0], list(operands[1:])
    else:
        paths = operands

    resolved: List[str] = []
    unresolved: List[str] = []
    for token in paths:
        if token in (".", "./") or os.path.lexists(os.path.join(cwd, token)):
            resolved.append(token)
        elif source:
            # A path operand after an explicit source is unambiguous by git's own grammar —
            # never a second ref — so there is no "is this actually a branch" question to
            # ask here the way there is for the no-source form below. A path git would refuse
            # to resolve is still worth passing through so the modified-file check downstream
            # can decide, rather than silently dropping it.
            resolved.append(token)
        elif _run(["git", "rev-parse", "--verify", "--quiet", token + "^{commit}"], cwd=cwd)[0]:
            continue                      # a branch or a commit: nothing on disk is touched
        else:
            unresolved.append(token)
    return Restoring(resolved, source, "", unresolved)


def _modified(paths: Sequence[str], cwd: str) -> List[Tuple[str, str]]:
    """(path, porcelain status) for every tracked change under these pathspecs.

    `--porcelain -z` rather than a line split, because a rename carries TWO paths in one
    record and a path may contain a space — reading those wrong would mean a refusal naming a
    file the command does not touch.
    """
    ok, out = _run(["git", "status", "--porcelain", "-z", "--"] + list(paths), cwd=cwd)
    if not ok:
        return []
    fields = out.split("\0")
    changed: List[Tuple[str, str]] = []
    index = 0
    while index < len(fields):
        record = fields[index]
        index += 1
        if len(record) < 4:
            continue
        status, path = record[:2], record[3:]
        if status[0] in ("R", "C"):
            index += 1                     # the rename's source, which is the next field
        if status in ("??", "!!"):
            continue                       # untracked or ignored: there is nothing to lose
        changed.append((path, status))
    return changed


def _diffstat(path: str, cwd: str) -> str:
    """`N added, M removed` across the index and the working tree, or `""`.

    THE FIGURE IS WHY THE REFUSAL LANDS. "240 lines" is what made the 2026-09-06 incident
    legible after the fact; saying it before the command runs is the whole point.
    """
    added = removed = 0
    for extra in ([], ["--cached"]):
        ok, out = _run(["git", "diff", "--numstat"] + extra + ["--", path], cwd=cwd)
        if not ok:
            continue
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                added += int(parts[0])
                removed += int(parts[1])
    if not added and not removed:
        return ""
    return "{0} added, {1} removed".format(added, removed)


def clause_checkout(reading: "shell_parse.Reading", cwd: str) -> Verdict:
    refusals: List[Refusal] = []
    notes: List[str] = []
    for placed in reading.placed:
        argv = shell_parse.strip_prefixes(placed.stage.argv)
        verb, rest = shell_parse.git_verb(argv)
        if verb not in _RESTORE_VERBS:
            continue
        where = shell_parse.git_cwd(argv) or cwd
        if not os.path.isdir(where):
            notes.append("`{0}` names a directory this guard cannot read, so it has no "
                         "opinion about it".format(shell_parse.short(placed.stage.text)))
            continue
        read = _read_restore(verb, rest, where)
        if read.passes:
            continue
        for token in read.unresolved:
            # THE NON-VACUITY LINE. Zero resolved operands on a command that has one is a
            # parse failure, and a guard that cannot say so is indistinguishable from a guard
            # that found nothing to object to.
            notes.append("`{0}` — `{1}` resolves to neither a path in this tree nor a "
                         "commit, so this guard has no opinion about it"
                         .format(shell_parse.short(placed.stage.text), token))
        if not read.paths:
            continue
        changed = _modified(read.paths, where)
        if not changed:
            continue
        lines = ["  git {0} — {1}".format(verb, shell_parse.short(placed.stage.text))]
        for path, status in changed[:8]:
            stat = _diffstat(path, where)
            lines.append("      {0} is {1}{2}".format(
                path, _porcelain(status), " ({0} lines)".format(stat) if stat else ""))
        if len(changed) > 8:
            lines.append("      and {0} more".format(len(changed) - 8))
        if read.source_named:
            lines.append("      `{0}` is named as the source, but that only means the "
                         "REPLACEMENT is known — the file it overwrites still had "
                         "uncommitted changes, and those are gone exactly the same way."
                         .format(read.source_named))
        else:
            lines.append("      Nothing names a source, so this restores from the index and "
                         "those changes are gone.")
        lines.extend([
            "",
            "  On 2026-09-06 `git checkout cli/cmd_reprice.py` put one mutation back and took",
            "  ~240 lines of that session's uncommitted work with it. Every other file "
            "survived,",
            "  which made it look at first like a smaller problem than it was.",
            "",
            "  A later session repeated the same shape with an explicit source —",
            "  `git checkout origin/main -- .` — over a tree that happened to be clean at",
            "  that moment, which is the only reason nothing was lost. Naming a source",
            "  changes what gets written; it does not change whether something existing is",
            "  discarded first.",
            "",
            "  Put a mutation back with a COPY, which cannot reach anything you did not copy:",
            "      sed -i.bak 's/OLD/NEW/' path/to/file.py     # run the check",
            "      mv path/to/file.py.bak path/to/file.py",
            "  and where sed cannot express the edit, `cp file file.bak` … `cp file.bak file`.",
            "  To look at another ref's content without touching the working tree at all:",
            "      git show <ref>:<path>",
            "  Committing first is the better fix: work in this repo lands in long "
            "uncommitted",
            "  stretches, so a checkout over a working file is almost always destroying "
            "something.",
        ])
        refusals.append(Refusal(
            "checkout", lines,
            "BLOCKED: this would discard uncommitted work, and git will not ask first."))
    return Verdict(refusals, notes)


def _porcelain(status: str) -> str:
    staged, tree = status[0], status[1]
    if staged != " " and staged != "?" and tree not in (" ", "?"):
        return "modified, with changes staged as well"
    if staged not in (" ", "?"):
        return "staged" + (" for deletion" if staged == "D" else "")
    return "modified" + (" (deleted)" if tree == "D" else "")


# ------------------------------------------------------------ 2. a write outside this tree

def _absolute(where: str, shell_cwd: str) -> str:
    """Expand and absolutize one directory taken from a command.

    LIFTED from the parent's `hooks/guard.py:_absolute`, minus its Git Bash drive-letter
    branch, which has no subject on this machine.
    """
    where = os.path.expandvars(os.path.expanduser(where))
    if not os.path.isabs(where) and shell_cwd:
        where = os.path.join(shell_cwd, where)
    return where


def _cd_operand(argv: Sequence[str]) -> Optional[str]:
    """The directory a `cd` stage moves to, or None when this stage is not a resolvable `cd`.

    `cd` alone goes home and `cd -` goes back: both are somewhere this parse cannot name, and
    they return `""` so the caller stops resolving relative targets rather than resolving
    them against the wrong directory. A flag (`cd -P dir`) is stepped over.
    """
    words = shell_parse.strip_prefixes(argv)
    if not words or words[0] != "cd":
        return None
    operands = [word for word in words[1:] if not word.startswith("-") or word == "-"]
    if not operands or operands[0] == "-":
        return ""
    target = operands[0]
    if "$" in target or "*" in target or "?" in target or "`" in target:
        return ""                          # unexpanded by this parse; no honest answer
    return target


class Write(NamedTuple):
    target: str
    cwd: str            # what a relative target is relative to; `""` when that is unknown


def _write_targets(reading: "shell_parse.Reading", cwd: str) -> Tuple[List[Write], List[str]]:
    """Every path this command would WRITE, as far as a parse can say, and every `cd`.

    TWO POSITIONS AND A DECLARED GAP. A redirection target is unambiguous, and `tee`'s
    operands are its whole purpose. `cp`, `mv`, `install`, `rsync` and `sed -i` are NOT read
    here: their destination is positional and mixed in with patterns and flags, and a clause
    that guessed wrong would refuse an ordinary copy. The Write|Edit half of this clause needs
    no parsing at all, which is why it is the half that cannot be skirted, and
    D179 names this gap rather than leaving it to be discovered.

    THE STAGES ARE WALKED IN ORDER AND A `cd` MOVES THE DIRECTORY EVERY LATER RELATIVE TARGET
    RESOLVES AGAINST. The 2026-09-06 incident this clause exists for was spelled
    `cd <main checkout> && …`, with every write after it RELATIVE — and until 2026-09-19 a
    relative target was resolved against the session's own cwd, so that exact shape passed.
    The parent's `hooks/guard.py:_run_dir` reads the last `cd` with a regular expression; this
    reads it off the parsed stage instead, because a regex over the raw string would find a
    `cd` inside a quoted script body, which is the defect this same change fixes.
    """
    writes: List[Write] = []
    moves: List[str] = []
    here: str = cwd
    for placed in reading.placed:
        stage = placed.stage
        moved = _cd_operand(stage.argv)
        if moved is not None:
            here = _absolute(moved, here) if moved and here else ""
            if here:
                moves.append(here)
            continue
        for redirect in (stage.fd1, stage.fd2):
            if redirect.kind == shell_parse.FILE and redirect.path:
                writes.append(Write(redirect.path, here))
        argv = shell_parse.strip_prefixes(stage.argv)
        if argv and (argv[0] == "tee" or argv[0].endswith("/tee")):
            writes.extend(Write(word, here) for word in argv[1:] if not word.startswith("-"))
    return writes, moves


def _resolve_target(target: str, cwd: str) -> str:
    """A write target resolved without requiring it to exist yet."""
    path = target if os.path.isabs(target) else os.path.join(cwd, target)
    parent = _real(os.path.dirname(path) or cwd)
    return os.path.join(parent, os.path.basename(path))


def _outside(target: str, cwd: str, root: str) -> Optional[Tuple[str, str]]:
    """(resolved target, why it is outside) — or None when the write is in bounds."""
    if "$" in target or "*" in target or "?" in target:
        return None                        # unexpanded by this parse; no honest answer
    if not cwd and not os.path.isabs(target):
        return None                        # relative to a directory this parse cannot name
    resolved = _resolve_target(target, cwd)
    if _under(resolved, root):
        return None
    if _sanctioned_outside(resolved):
        return None
    return resolved, ""


def _tree_refusal(resolved: str, root: str, how: str,
                  heading: str = "BLOCKED: this would write outside the checkout this session "
                                 "is standing in.") -> Refusal:
    return Refusal("tree", [
        "  {0}".format(how),
        "      resolves to  {0}".format(resolved),
        "      this checkout is  {0}".format(root),
        "",
        "  On 2026-09-06 an absolute-path `cd` prefix wrote ~1,500 lines into the owner's "
        "MAIN",
        "  checkout, on `main`, for most of a session — and `make launch-agent`'s supervisor",
        "  hot-reloaded that uncommitted branch code into their live :8000 capture server "
        "while",
        "  they were using the app over their real store. The symptom was silent: this "
        "tree's",
        "  own dev server went on serving this tree's unedited app.",
        "",
        "  Every checkout has its own store, its own ports and its own inventory (D43), so "
        "the",
        "  tree you are standing in is the tree to edit — write the same path relative to "
        "it.",
        "  When you genuinely need another checkout, keep it READ-ONLY: `git show`,",
        "  `sqlite3 -readonly`, `git -C <tree> log`.",
    ], heading)


def clause_tree_bash(reading: "shell_parse.Reading", cwd: str, root: str) -> Verdict:
    if not root:
        return Verdict([], ["this guard could not resolve a checkout root for {0}, so it has "
                            "no opinion about where a write lands".format(cwd)])
    refusals: List[Refusal] = []
    writes, moves = _write_targets(reading, cwd)
    for write in writes:
        verdict = _outside(write.target, write.cwd, root)
        if verdict:
            refusals.append(_tree_refusal(verdict[0], root, "`{0}`".format(write.target)))
    # A `cd` INTO ANOTHER CHECKOUT IS THE INCIDENT'S FIRST WORD, and it is refused as an act
    # rather than as a prefix: the Bash tool's working directory persists between calls, so a
    # bare `cd <other tree>` leaves the session standing there for every command after it,
    # and `cd <other tree> && npm run build` writes that tree's `app/dist/` with no `>` for
    # the redirect reader to see. The predicate is resolution — `git rev-parse` at the target
    # — so a temp directory, `~/.claude` and a plain directory that is no checkout all pass,
    # and only a DIFFERENT checkout is refused. The read-only forms the refusal recommends
    # (`git -C <tree> log`, `git show`) never needed the `cd`.
    for moved in moves:
        resolved = _real(moved)
        if _under(resolved, root) or not os.path.isdir(resolved):
            continue
        # `_sanctioned_outside` and `_repo_holding` ask about a FILE's parent, so a directory
        # is posed as `<dir>/.` — otherwise a temp checkout's own root would read as "a temp
        # directory that belongs to no checkout", and this clause's own fixture could not pose
        # its case (D157, one register up).
        probe = os.path.join(resolved, ".")
        if _sanctioned_outside(probe):
            continue
        other = _repo_holding(probe)
        if not other or other == root:
            continue
        refusals.append(_tree_refusal(
            resolved, root, "`cd {0}` stands this session in another checkout".format(moved),
            "BLOCKED: this would stand in another checkout, and everything after the `cd` "
            "runs there."))
    return Verdict(refusals, [])


def clause_tree_write(file_path: str, cwd: str, root: str) -> Verdict:
    """The Write|Edit half: no command parsing at all, so no shell form can skirt it."""
    if not file_path:
        return Verdict([], [])
    if not root:
        return Verdict([], ["this guard could not resolve a checkout root for {0}, so it has "
                            "no opinion about {1}".format(cwd, file_path)])
    verdict = _outside(file_path, cwd, root)
    if not verdict:
        return Verdict([], [])
    return Verdict([_tree_refusal(verdict[0], root, file_path)], [])


# ------------------------------------------------------------------- 3. `gh api` with a field

_FIELD_FLAGS = {"-f", "-F", "--field", "--raw-field"}
_METHOD_FLAGS = {"-X", "--method"}


def clause_gh(reading: "shell_parse.Reading") -> Verdict:
    refusals: List[Refusal] = []
    for placed in reading.placed:
        argv = shell_parse.strip_prefixes(placed.stage.argv)
        if not argv or not (argv[0] == "gh" or argv[0].endswith("/gh")):
            continue
        if argv[1:2] != ["api"]:
            continue
        rest = argv[2:]
        fields: List[str] = []
        endpoint = ""
        has_method = False
        index = 0
        while index < len(rest):
            token = rest[index]
            index += 1
            if token in _METHOD_FLAGS or any(token.startswith(f + "=") for f in _METHOD_FLAGS):
                has_method = True
                if "=" not in token and index < len(rest):
                    index += 1
                continue
            if token.startswith("-X") and len(token) > 2:
                has_method = True
                continue
            if token in _FIELD_FLAGS:
                if index < len(rest):
                    fields.append(rest[index])
                    index += 1
                continue
            if any(token.startswith(flag + "=") for flag in ("--field", "--raw-field")):
                fields.append(token.split("=", 1)[1])
                continue
            if re.match(r"^-[fF].+", token) and not token.startswith("--"):
                fields.append(token[2:])
                continue
            if token.startswith("-"):
                # Another gh flag. `--paginate`, `--jq`, `--cache`, `-H` and friends: `-H`
                # and `--hostname` take a value, and stepping over a value that is really the
                # endpoint would lose the endpoint — which costs a less specific refusal and
                # never a wrong verdict.
                if token in ("-H", "--header", "--hostname", "--jq", "-q", "--template",
                             "-t", "--cache", "--input", "--slurp"):
                    index += 1
                continue
            if not endpoint:
                endpoint = token
        if has_method or not fields:
            continue
        if endpoint == "graphql":
            continue                       # a POST by design, and it carries no --method
        query = "&".join(fields)
        joined = endpoint + ("&" if "?" in endpoint else "?") + query if endpoint else query
        refusals.append(Refusal("gh", [
            "  {0}".format(shell_parse.short(placed.stage.text)),
            "      {0} gives this request a BODY, and gh sends a body with POST.".format(
                ", ".join("`{0}`".format(f) for f in fields)),
            "      No method is named, so the method is not the GET you meant.",
            "",
            "  A GET's parameters belong in the query string:",
            "      gh api '{0}'".format(joined),
            "  or name the method, if the body is what you wanted:",
            "      gh api --method GET {0} {1}".format(
                endpoint or "<endpoint>", " ".join("-f " + f for f in fields)),
            "",
            "  On 2026-09-12 the first form hung past a 120s tool timeout and left a "
            "background",
            "  process to reap, which reads as a network problem rather than as a malformed",
            "  request. It was hit while building the SHA-pinned merge wait, so it blocked a "
            "fix.",
        ], "BLOCKED: `gh api` with a field and no method is a POST."))
    return Verdict(refusals, [])


# ------------------------------------------------------------------ 4. `ln -s` over a path

def clause_link(reading: "shell_parse.Reading", cwd: str) -> Verdict:
    refusals: List[Refusal] = []
    for placed in reading.placed:
        argv = shell_parse.strip_prefixes(placed.stage.argv)
        if not argv or not (argv[0] == "ln" or argv[0].endswith("/ln")):
            continue
        symbolic = safe = False
        operands: List[str] = []
        for token in argv[1:]:
            if token.startswith("--"):
                if token == "--symbolic":
                    symbolic = True
                elif token in ("--force", "--no-dereference", "--interactive",
                               "--no-target-directory", "--backup"):
                    safe = True
                continue
            if token.startswith("-") and len(token) > 1:
                letters = set(token[1:])
                symbolic = symbolic or "s" in letters
                # `-f` replaces, `-n`/`-h` refuses to descend into a link to a directory, and
                # `-i` asks. Each of those is the caller saying what should happen to a path
                # that is already there, which is the whole ask of this clause.
                safe = safe or bool(letters & {"f", "n", "h", "i"})
                continue
            operands.append(token)
        if not symbolic or safe or not operands:
            continue
        if len(operands) == 1:
            pairs = [(operands[0], os.path.basename(operands[0].rstrip("/")))]
        elif len(operands) == 2:
            pairs = [(operands[0], operands[1])]
        else:
            directory = operands[-1]
            pairs = [(src, os.path.join(directory, os.path.basename(src.rstrip("/"))))
                     for src in operands[:-1]]
        for source, dest in pairs:
            if "$" in dest or "*" in dest:
                continue                   # unexpanded by this parse; no honest answer
            full = dest if os.path.isabs(dest) else os.path.join(cwd, dest)
            if not os.path.lexists(full):
                continue
            nested = ""
            if os.path.isdir(full) and not os.path.islink(full):
                nested = os.path.join(dest, os.path.basename(source.rstrip("/")))
            refusals.append(Refusal("link", [
                "  {0}".format(shell_parse.short(placed.stage.text)),
                "      `{0}` already exists.".format(dest),
            ] + ([
                "      It is a DIRECTORY, so ln does not fail — it creates `{0}` inside it, "
                "pointing".format(nested),
                "      at `{0}`. That is the 2026-08-29 incident exactly.".format(source),
            ] if nested else [
                "      ln will refuse it, or replace something you did not mean to replace.",
            ]) + [
                "",
                "  On 2026-08-29 `ln -s <main>/harness/images harness/images` over an "
                "existing",
                "  directory made `harness/images/images`. A copy brought the loop back, "
                "`Path.mkdir(",
                "  exist_ok=True)` raised FileExistsError, T1 died naming only the symptom, "
                "and iCloud",
                "  renamed the real 133 MB directory — the largest thing in this tree with no "
                "backup",
                "  anywhere — to `images 2`, empty.",
                "",
                "  Say which one you mean:",
                "      ln -sfn {0} {1}      # replace the link; never descend into it".format(
                    source, dest),
                "      [ -e {0} ] || ln -s {1} {0}".format(dest, source),
                "  `scripts/worktree-provision.sh` takes the second form, which is why "
                "`make worktree-setup`",
                "  has never reproduced this.",
            ], "BLOCKED: `ln -s` at a path that already exists."))
    return Verdict(refusals, [])


# ------------------------------------------------------------------------ 5. a polling loop

_PATTERN_POLLERS = {"pgrep", "pkill", "lsof"}
_BOUND_TOKENS = {"-ge", "-gt", "-le", "-lt", "-eq", "-ne", "break", "date", "seq", "timeout",
                 "SECONDS", "-m", "--max-time", "return", "exit"}
_SCRIPT_RUNNERS = {"bash", "sh", "zsh", "ksh", "dash"}


class Loop(NamedTuple):
    condition: List[str]
    body: List[str]
    kind: str                  # `while` or `until`
    text: str


def _loops(tokens: Sequence[str]) -> List[Loop]:
    """Every `while`/`until` … `do` … `done` in a token stream, nesting respected.

    `for` IS ABSENT ON PURPOSE. A `for` walks a word list and ends; it is bounded by
    construction, and the coordinator's own must-pass case (`for i in 1 2 3; do … sleep 2;
    done`) is a bounded retry this repo writes deliberately. Refusing one would be refusing
    the shape the refusal recommends.
    """
    found: List[Loop] = []
    for start, token in enumerate(tokens):
        if token not in ("while", "until"):
            continue
        depth = 0
        do_at = -1
        end = -1
        for index in range(start + 1, len(tokens)):
            word = tokens[index]
            if word in ("while", "until", "for") and do_at >= 0:
                depth += 1
            elif word == "do" and do_at < 0:
                do_at = index
            elif word == "done":
                if depth:
                    depth -= 1
                else:
                    end = index
                    break
        if do_at < 0 or end < 0:
            continue
        found.append(Loop(list(tokens[start + 1:do_at]), list(tokens[do_at + 1:end]), token,
                          " ".join(tokens[start:end + 1])))
    return found


def _sleeps(body: Sequence[str]) -> bool:
    return any(word == "sleep" or word.endswith("/sleep") for word in body)


def _polls_a_pattern(condition: Sequence[str]) -> str:
    """The pattern poller in a loop's condition, or `""`.

    `ps` IS CLASSIFIED BY ITS FLAGS AND NOT BY ITS NAME, because the sanctioned wait is a
    `ps`: `ps -p $PID` asks about one process this session started and `ps -ef` asks the whole
    machine. Reading them alike would refuse the one form the memory file names as allowed.
    """
    for index, word in enumerate(condition):
        if word in _PATTERN_POLLERS or any(word.endswith("/" + p) for p in _PATTERN_POLLERS):
            return word
        if word == "ps" or word.endswith("/ps"):
            # THE FLAGS ARE `ps`'S OWN AND STOP AT THE PIPE. `while ps -ef | grep -q x` puts a
            # `-q` in the token stream that belongs to `grep`, and reading it as ps's pid
            # selector made this exact case pass — the one shape the incident's author would
            # most plausibly reach for after being refused a `pgrep`.
            selector = False
            for token in condition[index + 1:]:
                if shell_parse.is_operator(token):
                    break
                if token.startswith("-p") or token.startswith("-q"):
                    selector = True
            if not selector:
                return "ps"
    return ""


def _bounded(loop: Loop) -> str:
    """What bounds this loop, or `""` — and `""` is the only thing that can be refused."""
    words = loop.condition + loop.body
    if any(word in _BOUND_TOKENS for word in words):
        return "a counter, a deadline or a break"
    for index, word in enumerate(loop.condition):
        if (word == "ps" or word.endswith("/ps")) and any(
                token.startswith("-p") for token in loop.condition[index + 1:]):
            return "a pid"
        if word == "kill" and "-0" in loop.condition:
            return "a pid"
    return ""


def _script_loops(argv: Sequence[str], cwd: str) -> List[Tuple[str, Loop]]:
    """The loops inside a shell script this command runs, read from the file.

    THE INCIDENT'S COMMAND CARRIED NO LOOP AT ALL: it was `bash scratchpad/autodrive.sh`, and
    the `while`/`sleep` was in the file. Resolving the file is reap.py's standard — ask the
    system rather than the string — and it is the only reading that can see the thing that
    ran for four hours.

    ONLY A SHELL SCRIPT IS READ. A Python supervisor's loop is a different grammar and is not
    guessed at: `make up` runs one on purpose, and `make design-check ARGS=--wait` queues on
    another. Neither is a `make` target this file resolves, and both are shapes CLAUDE.md
    tells a session to background.
    """
    words = list(argv)
    if words and (words[0] in _SCRIPT_RUNNERS or os.path.basename(words[0]) in _SCRIPT_RUNNERS):
        words = [w for w in words[1:] if not w.startswith("-")]
    out: List[Tuple[str, Loop]] = []
    for word in words[:4]:
        if not word.endswith((".sh", ".bash")) and "/" not in word:
            continue
        path = word if os.path.isabs(word) else os.path.join(cwd, word)
        try:
            if not os.path.isfile(path) or os.path.getsize(path) > 262144:
                continue
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not (word.endswith((".sh", ".bash")) or text.startswith("#!") and "sh" in
                text.splitlines()[0]):
            continue
        tokens, _ = shell_parse.tokenize(text)
        for loop in _loops(tokens):
            out.append((word, loop))
    return out


def detached(command: str, backgrounded: bool) -> bool:
    """Whether this command outlives the turn that typed it.

    TWO DOORS AND ONE NOTION: the harness's own `run_in_background`, and a trailing `&`. The
    2026-09-12 runaway came through the first, which is the door a session reaches for when a
    command is slow — so a reading that saw only the shell's `&` would have been blind to the
    incident it exists for.
    """
    return backgrounded or bool(re.search(r"&\s*$", command.strip()))


def clause_wait(reading: "shell_parse.Reading", command: str, cwd: str,
                backgrounded: bool) -> Verdict:
    refusals: List[Refusal] = []
    tokens, _ = shell_parse.tokenize(command)
    inline = _loops(tokens)
    outliving = detached(command, backgrounded)

    for loop in inline:
        if not _sleeps(loop.body):
            continue
        poller = _polls_a_pattern(loop.condition)
        if poller:
            refusals.append(Refusal("wait", [
                "  {0}".format(shell_parse.short(loop.text)),
                "      the condition polls a PATTERN with `{0}`, which matches every process "
                "whose".format(poller),
                "      command line NAMES it — an editor with that file open, a `grep` for "
                "it, this",
                "      session's own wrapper for this very command, a second copy of the "
                "thing you",
                "      are waiting for. The pattern is not the process, so the condition can "
                "stay",
                "      true long after the work has finished and whatever is chained after "
                "the loop",
                "      never runs.",
                "      (And WHICH of those matches is platform-dependent: BSD `pgrep` "
                "excludes itself",
                "      and its own ancestors unless `-a` is given, so the answer depends on "
                "the process",
                "      tree your harness happens to build. That is the argument, not a "
                "detail.)",
                "",
                "  On 2026-09-12 a session that had read that rule four days earlier wrote",
                "  `until ! pgrep -f 'scratchpad/drive.sh'`. The loop never fired, a second "
                "copy of",
                "  the driver raced a live one for ~15 minutes, and the owner caught it.",
            ] + _WAIT_ADVICE, "BLOCKED: a polling loop over a pattern cannot know what it "
                              "matched."))
            continue
        if outliving and not _bounded(loop):
            refusals.append(Refusal("wait", [
                "  {0}".format(shell_parse.short(loop.text)),
                "      backgrounded, and the loop has no counter, no deadline and no pid to",
                "      outlive — so nothing ends it and nothing in this repo can see it "
                "afterwards.",
            ] + _RUNAWAY + _WAIT_ADVICE,
                "BLOCKED: a backgrounded polling loop with nothing to end it."))

    if outliving:
        # EVERY STAGE, NOT THE FIRST. `cd /x && bash driver.sh &` puts the `cd` in stage one
        # and the driver in stage two, and a session backgrounding a script very often spells
        # it that way. Reading only the head would have been blind to the incident's command
        # wearing one extra word.
        scripts: List[Tuple[str, Loop]] = []
        for placed in reading.placed:
            scripts.extend(_script_loops(shell_parse.strip_prefixes(placed.stage.argv), cwd))
        for name, loop in scripts:
            if not _sleeps(loop.body) or _bounded(loop):
                continue
            refusals.append(Refusal("wait", [
                "  {0}".format(shell_parse.short(command.strip().replace("\n", " "))),
                "      `{0}` contains {1}".format(name, shell_parse.short(loop.text, 60)),
                "      backgrounded, and that loop has no counter, no deadline and no pid to",
                "      outlive — so nothing ends it and nothing in this repo can see it "
                "afterwards.",
            ] + _RUNAWAY + _WAIT_ADVICE,
                "BLOCKED: a backgrounded script whose loop has nothing to end it."))
    return Verdict(refusals, [])


_RUNAWAY = [
    "",
    "  On 2026-09-12 a backgrounded `while`/`sleep` merge driver ran 119 rounds over 3h58m,",
    "  across a compaction of the session that started it, racing that session's own merges "
    "and",
    "  re-resolving branches it was resolving. A human noticed a four-hour bash in their own "
    "UI.",
    "  (`make janitor` finds a poller that is ALREADY running and that nobody owns any more "
    "— D175.",
    "  This refuses the one being created, which is the half no sweep can reach.)",
]

_WAIT_ADVICE = [
    "",
    "  Background the WORK and take its completion notification. A backgrounded command",
    "  re-invokes this session when it EXITS, and carries its result; a poll produces one "
    "wake-up",
    "  per round, none of which carry anything. For the state of the merge queue,",
    "  `make coordinator` READS the repo — main, every open PR with a SHA-pinned verdict, the",
    "  worktrees, the live sessions — rather than composing a report out of a driver's stdout.",
    "",
    "  A wait on a pid this session started is the sanctioned form, and it is bounded by the",
    "  process rather than by a pattern:",
    "      while ps -p $PID >/dev/null; do sleep 5; done",
]


# ------------------------------------------------------- 6. a push to the wrong branch name

# Flags git push takes that consume the NEXT token. `--force-with-lease` and friends can
# also take a value with `=`, handled by the `=`-prefix check below rather than listed twice.
_PUSH_VALUE_FLAGS = {"--repo", "-o", "--push-option", "--receive-pack", "--exec",
                     "--recurse-submodules"}

# Flags that take no value and say nothing about WHICH branch this pushes. `--all`,
# `--mirror`, `--tags` and `-d`/`--delete` are handled separately below: each of them pushes
# something other than "this branch under its own name", so this clause has nothing to say
# about them and reading them as ordinary flags would misread the operand that follows.
_PUSH_BARE_FLAGS = {"-f", "--force", "--force-with-lease", "--force-if-includes", "-u",
                    "--set-upstream", "-n", "--dry-run", "-q", "--quiet", "-v", "--verbose",
                    "--porcelain", "--atomic", "--no-verify", "--thin", "--no-thin",
                    "--progress", "--no-progress", "-4", "--ipv4", "-6", "--ipv6",
                    "--signed", "--no-signed", "--follow-tags", "--prune"}
_PUSH_SPECIAL_FLAGS = {"--all", "--mirror", "--tags", "-d", "--delete"}


def _push_operands(rest: Sequence[str]) -> Tuple[str, List[str], bool]:
    """(remote, refspecs, special) for a `git push` invocation.

    `special` marks a flag that pushes something other than "this branch under its own
    name" — `--all`, `--mirror`, `--tags`, `-d`/`--delete` — which is a different operation
    this clause has no opinion about. AN UNKNOWN FLAG IS STEPPED OVER, the fail-open reading
    `clause_gh` already takes for `gh api`'s own long tail of flags: the worst outcome is a
    push this clause says nothing about, never a wrong verdict.
    """
    remote = ""
    refspecs: List[str] = []
    special = False
    index = 0
    while index < len(rest):
        token = rest[index]
        index += 1
        if token in _PUSH_SPECIAL_FLAGS:
            special = True
            continue
        if token in _PUSH_VALUE_FLAGS:
            index += 1
            continue
        if any(token.startswith(flag + "=") for flag in _PUSH_VALUE_FLAGS):
            continue
        if token in _PUSH_BARE_FLAGS or _flag_value(token, _PUSH_BARE_FLAGS):
            continue
        if token.startswith("-"):
            continue
        if not remote:
            remote = token
        else:
            refspecs.append(token)
    return remote, refspecs, special


def _tracked_branch(branch: str, remote: str, cwd: str) -> Optional[str]:
    """The branch name `branch` is configured to track on `remote`, or `None`.

    `None` covers two cases this clause reads alike: no upstream configured at all — the
    ordinary first push of a new branch — and an upstream configured for a DIFFERENT remote,
    which is a fork workflow this clause has no business in. Neither is the incident's shape:
    the trap is a mismatch on the SAME remote the command is about to push to.
    """
    remote_ok, remote_out = _run(
        ["git", "config", "--get", "branch.{0}.remote".format(branch)], cwd=cwd)
    if not remote_ok or remote_out.strip() != remote:
        return None
    merge_ok, merge_out = _run(
        ["git", "config", "--get", "branch.{0}.merge".format(branch)], cwd=cwd)
    if not merge_ok or not merge_out.strip():
        return None
    tracked = merge_out.strip()
    if tracked.startswith("refs/heads/"):
        tracked = tracked[len("refs/heads/"):]
    return tracked


def _default_branch(remote: str, cwd: str) -> str:
    """The branch this checkout treats as the remote's default, or "" if it cannot tell.

    `refs/remotes/<remote>/HEAD` is git's OWN record of it — set by `git clone`, or by
    `git remote set-head <remote> -a` — and is specific to the remote actually being pushed
    to, which matters for a fork workflow whose fork defaults to a different branch than
    `origin`'s. A throwaway repo that has never had that symbolic ref written (this guard's
    own selftest fixture, most `git init`-then-`push` clones) falls back to the same rule
    `scripts/janitor.py:default_branch` already uses for the primary checkout: the first of
    `main`, `master` that exists as a local branch. Nothing here is a guess dressed as a
    read — an unreadable remote and an absent local branch both return "", and the caller
    treats that exactly like the pre-2026-09-13 code did: no exemption, still refused.
    """
    ok, out = _run(["git", "symbolic-ref", "--quiet", "--short",
                    "refs/remotes/{0}/HEAD".format(remote)], cwd=cwd)
    if ok and out.strip():
        head = out.strip()
        prefix = remote + "/"
        return head[len(prefix):] if head.startswith(prefix) else head
    for name in ("main", "master"):
        ok, _ = _run(["git", "rev-parse", "--verify", "--quiet",
                      "refs/heads/" + name], cwd=cwd)
        if ok:
            return name
    return ""


def _push_refusal(text: str, remote: str, spec: str, branch: str, tracked: str) -> Refusal:
    return Refusal("push", [
        "  {0}".format(text),
        "      the current branch is `{0}`; its tracked upstream is `{1}/{2}` — a DIFFERENT "
        "name.".format(branch, remote, tracked),
        "      naming `{0}` here does not push to that upstream. It pushes HEAD to "
        "`{1}/{2}` instead —".format(spec, remote, branch),
        "      a BRAND NEW branch on {0}, or an update to a stray one already there. "
        "`{0}/{1}` is untouched.".format(remote, tracked),
        "",
        "  On 2026-09-12 a coordinator resolving a merge conflict stood on a local branch a",
        "  background agent had named `pr-h-readings-table-local`, whose configured upstream "
        "was",
        "  actually `origin/claude/pr-h-readings-table` — the agent had pushed its squashed "
        "commit",
        "  to the real PR branch under a name that never matched the local one. `git push "
        "origin",
        "  HEAD` reported success — `[new branch] HEAD -> pr-h-readings-table-local` — having",
        "  created a stray branch on origin and left the actual PR branch untouched. It was "
        "caught",
        "  only because the next command's output looked wrong.",
        "",
        "  Git's own `push.default=simple` refuses exactly this shape for a BARE `git push`",
        "  and prints the fix — but naming a refspec, even an unqualified `HEAD`, is git's "
        "own",
        "  signal that the caller knows what they want, and here that signal was wrong. Two "
        "real",
        "  fixes, both git's own:",
        "      git push                              # let git's safety net name the fix",
        "      git push {0} HEAD:{1}      # push to the branch actually tracked".format(
            remote, tracked),
    ], "BLOCKED: this pushes to a branch of the WRONG name, not the one tracked.")


def clause_push(reading: "shell_parse.Reading", cwd: str) -> Verdict:
    refusals: List[Refusal] = []
    notes: List[str] = []
    for placed in reading.placed:
        argv = shell_parse.strip_prefixes(placed.stage.argv)
        verb, rest = shell_parse.git_verb(argv)
        if verb != "push":
            continue
        where = shell_parse.git_cwd(argv) or cwd
        if not os.path.isdir(where):
            notes.append("`{0}` names a directory this guard cannot read, so it has no "
                         "opinion about it".format(shell_parse.short(placed.stage.text)))
            continue
        remote, refspecs, special = _push_operands(rest)
        if special or not remote or not refspecs:
            continue                       # no plain "push this branch" shape to judge
        ok, out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=where)
        branch = out.strip() if ok else ""
        if not branch or branch == "HEAD":
            continue                       # detached, or unresolvable: no opinion
        for spec in refspecs:
            if ":" in spec:
                continue                   # an explicit destination; this IS the fix, not the trap
            if spec != "HEAD" and spec != branch:
                continue                   # a different ref — not this clause's business
            tracked = _tracked_branch(branch, remote, where)
            if tracked is None or tracked == branch:
                continue                   # no upstream on this remote, or it already matches
            # THE ORDINARY FIRST PUSH OF A FEATURE BRANCH IS EXEMPT, amended 2026-09-13 (D179).
            # A branch cut with `git switch -c X origin/main` tracks `origin/main` from birth —
            # that is what "cut from" means — and its first push names its OWN branch, never
            # `main`. Before this line that push was refused, and the refusal's own remedy told
            # the operator to push at `main` by name (`git push origin HEAD:main`), which is the
            # one act D42, both git hooks and GitHub branch protection all exist to prevent. The
            # incident this clause exists for tracked a DIFFERENT FEATURE branch
            # (`claude/pr-h-readings-table`, not `main`), so keeping that shape refused needs
            # nothing here but excluding the default branch from it.
            if tracked == _default_branch(remote, where):
                continue
            refusals.append(_push_refusal(
                shell_parse.short(placed.stage.text), remote, spec, branch, tracked))
            break
    return Verdict(refusals, notes)


# --------------------------------------------------------- 7. a consuming/destructive stash

# Subcommands git itself recognises. Anything else after `stash` — a flag, or nothing at
# all — is the BARE form, which git reads as an implicit `push`.
_STASH_SUBCOMMANDS = {"push", "save", "pop", "apply", "drop", "clear", "list", "show",
                     "branch", "create", "store"}

# `pop` and `clear` are refused UNCONDITIONALLY — see the ruling below. `drop` is refused
# only with no explicit entry named; `push`/`save`/`apply`/`list`/`show`/`branch`/`create`/
# `store` never destroy an entry that already exists, so this clause has no opinion about
# them at all.
_STASH_ALWAYS = {"pop", "clear"}


def _stash_entries(cwd: str) -> Optional[List[str]]:
    """One subject line per entry, newest first. None when the stack cannot be read at all.

    THE RESOLUTION THIS CLAUSE WAS MISSING. Measured 2026-09-17, before this function
    existed: over an EMPTY stack, in a throwaway fixture where `git stash pop` answers
    "No stash entries found.", the clause refused `pop`, `clear`, `drop` and the bare form
    with exactly the verdicts it gives over a real entry — the two arms were byte-identical.
    A guard whose answer does not move when its subject does is testing the subcommand's
    NAME, which is the `\\bpkill\\b` defect `reap.py` exists to not be, and which
    `clause_checkout` and `clause_reset` both already avoid by reading
    `git status --porcelain` before they refuse.
    """
    ok, out = _run(["git", "stash", "list", "--format=%gs"], cwd=cwd)
    if not ok:
        return None
    return [line for line in out.splitlines() if line]


def _worktree_count(cwd: str) -> Optional[int]:
    """How many working trees share this clone's one stash stack.

    Derived rather than typed: the refusal used to assert "~30 working trees" as a constant,
    and the measurement on 2026-09-17 was 27. A number a reader is asked to believe is a
    number this guard can read for itself.
    """
    ok, out = _run(["git", "worktree", "list", "--porcelain"], cwd=cwd)
    if not ok:
        return None
    count = sum(1 for line in out.splitlines() if line.startswith("worktree "))
    return count or None


def _stash_refusal(text: str, why: List[str], heading: str,
                   trees: Optional[int] = None) -> Refusal:
    lines = ["  {0}".format(text)] + why + [
        "",
        "  The stash stack is per-CLONE, not per-worktree (D43 covers the store and the",
        "  ports; the stash was never split the same way) — this clone runs {0}, often".format(
            "{0} working tree{1}".format(trees, "" if trees == 1 else "s") if trees
            else "many working trees"),
        "  with a live session in each, all pushing onto ONE stack. An index",
        "  like `stash@{0}` names \"whatever is on top right now\", which is a different",
        "  entry from one call to the next as other sessions push and pop.",
        "",
        "  Set work aside with a commit on your own branch, never a stash. A stash entry",
        "  belongs to no branch, and it outlives no session that holds its tag:",
        "      git add -A && git commit -m \"WIP: <what this is>\"",
        "  A commit is addressed by its own sha, cannot be reinterpreted by somebody else's",
        "  push, and travels with the branch when you push it.",
    ]
    return Refusal("stash", lines, heading)


def clause_stash(reading: "shell_parse.Reading", cwd: str) -> Verdict:
    """`git stash pop`/`drop`/`clear`, and the bare form, refused; `push`/`apply` pass.

    THE RULING THE MODULE DOCSTRING ASKS FOR, WRITTEN HERE RATHER THAN THERE SO IT STAYS
    BESIDE THE CODE IT GOVERNS:

    `pop` is refused EVEN WHEN THE CALLER NAMES AN EXPLICIT ENTRY, unlike `drop` below. `pop`
    applies and drops in one atomic step — if the apply is wrong, the entry that would have
    let you recover is already gone, and naming it first does not buy back that window;
    "which entry" was never the risk `pop` carries, "no chance to check before it is gone"
    is. Use `apply <sha>` (never dropped, so the mistake is inspectable) then a `drop <sha>`
    once you have looked, which this clause DOES allow because `drop` names an explicit
    entry — `pop` cannot be split into those two steps, so its whole verb is refused.

    `clear` always refuses: it takes no target at all, so "no explicit entry" is not a
    condition to check, it is the whole command.

    `drop` refuses only bare (`stash@{0}` implied); a caller who types any operand at all —
    an index, a sha, whatever — has identified something, and RESOLUTION rather than
    spelling is what every other clause here does with an operand it cannot itself verify:
    reported if it fails to resolve, allowed either way, because "this guard could not
    confirm it" is not the same claim as "this destroys something".

    A bare `git stash` (no subcommand, implicit `push`) is refused too, and it destroys
    nothing — the reason is IDENTIFICATION, not survival. The same six characters are what a
    single-user habit types to mean "save my work" AND "get my stash back", and in a clone
    where entries pile up from other sessions an untagged, unindexed push is unfindable by
    anything but luck. `push -u -m <tag>` costs one flag and turns every entry into something
    `list`/`apply <sha>` can find again.
    """
    refusals: List[Refusal] = []
    notes: List[str] = []
    for placed in reading.placed:
        argv = shell_parse.strip_prefixes(placed.stage.argv)
        verb, rest = shell_parse.git_verb(argv)
        if verb != "stash":
            continue
        where = shell_parse.git_cwd(argv) or cwd
        if not os.path.isdir(where):
            notes.append("`{0}` names a directory this guard cannot read, so it has no "
                         "opinion about it".format(shell_parse.short(placed.stage.text)))
            continue
        sub = rest[0] if rest and rest[0] in _STASH_SUBCOMMANDS else ""
        text = shell_parse.short(placed.stage.text)
        trees = _worktree_count(where)
        # THE BARE FORM IS JUDGED BEFORE THE STACK IS READ, AND THAT ASYMMETRY IS THE POINT.
        # A bare `git stash` is an implicit PUSH: it CREATES an anonymous entry, so its
        # hazard is identification and not consumption, and an entry pushed onto an empty
        # stack is exactly as unfindable once other sessions push onto it. Gating it on
        # current depth would be reading the wrong subject — the stack it will join, not the
        # stack it finds.
        if sub == "":
            refusals.append(_stash_refusal(text, [
                "      no subcommand is named, so this is an implicit `push` — an",
                "      anonymous entry that nothing but luck finds again in a shared stack.",
            ], "BLOCKED: name what this does — `push`, `list`, `apply` — a bare `git stash` "
               "is ambiguous.", trees))
            continue
        # RESOLVE THE SUBJECT BEFORE REFUSING OVER IT — clause 1 and clause 8's standard,
        # which this clause did not meet until 2026-09-17. Everything below CONSUMES an
        # entry that already exists, so an empty stack is a pass: there is nothing on it to
        # destroy, and git itself answers "No stash entries found." An unreadable stack is
        # REPORTED rather than passed silently, per this guard's non-vacuity line.
        entries = _stash_entries(where)
        if entries is None:
            notes.append("`{0}` — this guard could not read the stash stack, so it has no "
                         "opinion about it".format(text))
            continue
        if not entries:
            continue
        if sub in _STASH_ALWAYS:
            if sub == "pop":
                why = [
                    "      `git stash pop` applies AND drops an entry in one atomic step —",
                    "      even a named one has no window to confirm the apply was right",
                    "      before the entry that would undo it is gone.",
                ]
            else:
                why = [
                    "      `git stash clear` destroys EVERY entry on the shared stack at",
                    "      once, including every other session's, and takes no target to",
                    "      narrow it.",
                ]
            refusals.append(_stash_refusal(
                text, why, "BLOCKED: this consumes or destroys a stash entry no caller here "
                          "identified.", trees))
            continue
        if sub == "drop":
            operand = [token for token in rest[1:] if not token.startswith("-")]
            if not operand:
                refusals.append(_stash_refusal(text, [
                    "      no entry is named, so this drops `stash@{0}` — the top of a",
                    "      stack every worktree in this clone shares.",
                ], "BLOCKED: this consumes or destroys a stash entry no caller here "
                   "identified.", trees))
    return Verdict(refusals, notes)


# --------------------------------------------------------------- 8. a hard-family reset

_RESET_DISCARDING_MODES = {"--hard", "--merge", "--keep"}


def _reset_refusal(text: str, mode: str, changed: List[Tuple[str, str]]) -> Refusal:
    lines = ["  {0}".format(text)]
    for path, status in changed[:8]:
        lines.append("      {0} is {1}".format(path, _porcelain(status)))
    if len(changed) > 8:
        lines.append("      and {0} more".format(len(changed) - 8))
    lines.extend([
        "",
        "  `reset {0}` overwrites the index AND the working tree from a commit, with no".format(
            mode),
        "  confirmation and no record of what it overwrote — `git checkout <path>`'s own",
        "  shape (rank 1 above) one register up: the whole tree instead of one file.",
        "",
        "  Mutation-test with a copy instead, which cannot reach anything you did not copy:",
        "      cp path/to/file.py path/to/file.py.bak    # before the mutation",
        "      cp path/to/file.py.bak path/to/file.py     # restore it after",
        "  Commit first when the work is real: `reset --hard` over a clean tree destroys",
        "  nothing, because there is nothing uncommitted left for it to overwrite.",
        "",
        "  NOTE: `scripts/githooks/reference-transaction` already refuses this shape when it",
        "  would MOVE A PROTECTED REF (`main`) — that hook and this clause see different",
        "  halves: the ref hook guards which commit a branch points at, this guards the",
        "  uncommitted work in the tree standing on it, and a reset can lose the second",
        "  while never touching the first.",
    ])
    return Refusal("reset", lines,
                   "BLOCKED: this would discard uncommitted work, and git will not ask first.")


def clause_reset(reading: "shell_parse.Reading", cwd: str) -> Verdict:
    """`git reset --hard`/`--merge`/`--keep` over a dirty tree, refused; everything else passes.

    THE RULING THE MODULE DOCSTRING ASKS FOR. A path-form reset — `git reset [<commit>] --
    <paths>...` — is NEVER refused, and that is not a gap: git itself refuses to combine a
    pathspec with `--hard`/`--merge`/`--keep` ("fatal: Cannot do hard reset with paths."), so
    the only mode a pathspec can ever reach is the mixed/soft one, which touches the INDEX
    and never the working tree. Unstaging a file cannot discard its content — the content on
    disk is exactly what it was before the command ran — so there is no discarding path-form
    case for this clause to catch, and every path-form shape below is pinned as PASSING for
    that reason rather than left untested. A bare `git reset` (no mode, no paths) is the same
    mixed default and passes the same way; `--soft` never touches the working tree either.

    So the whole predicate is: one of the three discarding modes, over a tree `git status`
    says is not clean. Untracked files are excluded on purpose — `--hard` never touches them
    (that is `git clean`'s job, not this clause's), and counting them would refuse a `--hard`
    that discards nothing.
    """
    refusals: List[Refusal] = []
    notes: List[str] = []
    for placed in reading.placed:
        argv = shell_parse.strip_prefixes(placed.stage.argv)
        verb, rest = shell_parse.git_verb(argv)
        if verb != "reset":
            continue
        where = shell_parse.git_cwd(argv) or cwd
        if not os.path.isdir(where):
            notes.append("`{0}` names a directory this guard cannot read, so it has no "
                         "opinion about it".format(shell_parse.short(placed.stage.text)))
            continue
        mode = next((token for token in rest if token in _RESET_DISCARDING_MODES), "")
        if not mode:
            continue                       # soft/mixed, or a path-form reset: nothing to lose
        changed = _modified([], where)
        if not changed:
            continue                       # a genuinely clean tree: nothing to lose either
        refusals.append(_reset_refusal(shell_parse.short(placed.stage.text), mode, changed))
    return Verdict(refusals, notes)


# ------------------------------------------------ 9. a narrated wait with nobody watching it
#
# `make merge` pushes a claim commit and then waits for THAT COMMIT's checks, which take four
# to five minutes on this repo (measured across 12 consecutive runs, 2026-09-20). Five to ten
# minutes of waiting is CORRECT and this clause does not touch it. What it refuses is the one
# spelling that makes correct waiting indistinguishable from a hang:
#
#     make merge ARGS="437 --confirm" 2>&1 | tail -18
#
# The wait narrates — `CHECK_HEARTBEAT_SECONDS = 60`, a line a minute naming what it is
# waiting on. A pipe makes the writer's stdout a pipe, Python block-buffers it, and `tail`
# then keeps only the last few lines of whatever finally arrives. Both halves of the
# heartbeat's job are lost: nothing appears WHILE it waits, and most of it is thrown away when
# it ends. On 2026-09-20 one session did this twice in an evening while knowing better, and
# the owner reports other sessions reaching the same conclusion — that the merge had hung —
# about a merge that was working.
#
# THE ROSTER IS NAMED AND IT IS DELIBERATELY SHORT, and this is the one clause in this file
# that does NOT resolve its subject from the system. It cannot: "does this command block for
# minutes while printing a heartbeat" is not a question the filesystem, `git` or the process
# table can answer about an arbitrary command before it runs. The alternative — refuse every
# pipe into `tail` — would fire on `git log | tail`, `make check | tail -40` and a hundred
# honest lines a day, and the house rule is explicit that a guard which goes red when nothing
# is wrong is SPENT, because the reader learns to scroll past it. So this follows
# `silent-write-guard.py`'s precedent instead: a roster of the acts that have actually gone
# wrong, one entry per incident, and a new entry when something new goes wrong through one.
# `make design-check` is the nearest candidate and is deliberately absent — it BACKGROUNDS
# itself and writes `.serve/design-check.json`, so its verdict survives a pipe.
#
# AND THE ROSTER IS RECONCILED RATHER THAN TRUSTED. `scripts/guard-shell-selftest.sh` asserts
# that every command named here still carries a heartbeat constant in the file that runs it —
# an entry that stops narrating stops being this clause's business, and that is a failing case
# rather than a stale sentence.
#
# WHAT COUNTS AS LOSING IT: stdout discarded (`/dev/null`, a closed descriptor, a file nothing
# in the same command reads back), or piped into a filter that keeps only an end of the
# stream. `| tee <file>` is NOT refused: it delays the narration but keeps every byte of it,
# and refusing the careful spelling of "keep the output" is how a guard teaches people to
# switch it off.

_TRUNCATING = {"tail", "head"}

# THE TABLE IS THE ROSTER, AND THE RESOLVER BELOW READS IT rather than carrying its own copy
# of the same names — the house rule that an allow list points at the constant the code emits,
# never at a duplicate of it. Each entry: the name a refusal prints, the `make` goal that runs
# it, the script that runs underneath that goal, and the heartbeat constant the self-test
# reconciles the entry against.
NARRATORS = (
    ("make merge", "merge", "scripts/merge-pr.py", "CHECK_HEARTBEAT_SECONDS"),
)


def _narrating(argv: Sequence[str]) -> str:
    """The name of the long, heartbeat-emitting command this stage runs, or `""`.

    `merge` EXACTLY, the way `silent-write-guard.py` reads the same word: `make
    merge-selftest` is a test of the wrapper and is over in seconds, and a prefix match would
    refuse it for being quiet — which is the finding that teaches a session to reach for the
    hatch.
    """
    argv = list(argv)
    if not argv:
        return ""
    # A PREVIEW IS NOT A WAIT, and that is resolved rather than assumed. `make merge ARGS=437`
    # presses nothing, asks GitHub two questions and returns in seconds — there is no
    # heartbeat to hide, so piping it is not this clause's business. Only `--confirm` reaches
    # the claim commit's wait. This is the narrowest the clause can be while still covering
    # the act that went wrong.
    if not any("--confirm" in word for word in argv):
        return ""
    head = argv[0]
    if head == "make" or head.endswith("/make"):
        goals = [word for word in argv[1:]
                 if not word.startswith("-") and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word)]
        for name, goal, _, _ in NARRATORS:
            if goal in goals:
                return name
        return ""
    # THE SCRIPT RUN DIRECTLY IS THE SAME ACT. `make merge` is a two-line recipe around
    # `python3 scripts/merge-pr.py`, and a session that has been refused the first spelling
    # reaches for the second.
    for _, _, script, _ in NARRATORS:
        base = os.path.basename(script)
        if any(word.endswith(base) for word in argv):
            return script
    return ""


def _sink(placed: "shell_parse.Placed", every: Sequence["shell_parse.Stage"]) -> Tuple[str, str]:
    """Where this stage's narration actually goes: `("", "")` when the session gets it.

    THE FATE IS THE PIPELINE'S AND NOT THE STAGE'S, which is why this takes a `Placed` rather
    than a `Stage` — `silent-write-guard.py` learned the same thing about the same parser.

    THE LINE IS LOSS, NEVER DELAY, and drawing it anywhere else makes this clause fire on
    honest work. `| tee <file>` and `> <file>` followed by a read of that same file both
    BUFFER the heartbeat — neither delivers it while the waiting is happening — and neither
    loses a byte of it. Refusing the careful spelling of "keep the output" is how a guard
    teaches a session to reach for its hatch. What is refused is the narration being GONE:
    thrown away, or cut down to one end of itself. (This is a different line from
    `silent-write-guard.py`'s, which asks whether EVIDENCE survives rather than whether a
    stream arrives, and the two agree on the file case for different reasons.)
    """
    where = placed.stage.fd1
    if where.kind == shell_parse.NULL:
        return "discarded", "/dev/null"
    if where.kind == shell_parse.CLOSED:
        return "discarded", "a closed descriptor"
    if where.kind == shell_parse.FILE:
        for other in every:
            if other is not placed.stage and where.path in other.argv:
                return "", ""
        return "redirected", "`{0}`, which nothing in this command reads back".format(where.path)
    if placed.pipe_op in shell_parse.PIPE_OPS:
        tail = shell_parse.strip_prefixes(placed.tail.argv)
        word = os.path.basename(tail[0]) if tail else ""
        if word in _TRUNCATING:
            return "truncated", "`{0}`, which keeps one end of the stream".format(word)
    return "", ""


def clause_narrate(reading: "shell_parse.Reading") -> Verdict:
    refusals: List[Refusal] = []
    seen: Set[str] = set()
    for placed in reading.placed:
        name = _narrating(shell_parse.strip_prefixes(placed.stage.argv))
        if not name:
            continue
        how, detail = _sink(placed, reading.every)
        if not how or name in seen:
            continue
        seen.add(name)
        refusals.append(Refusal("narrate", [
            "  {0}".format(shell_parse.short(placed.stage.text)),
            "      `{0}` blocks for MINUTES and narrates while it does — a line a minute "
            "naming".format(name),
            "      what it is waiting on. Here its stdout is {0} to {1}.".format(how, detail),
            "",
            "  A pipe or a redirect makes that stdout a pipe or a file, so Python "
            "block-buffers it:",
            "  nothing appears until the command EXITS, and a truncating filter then keeps "
            "only the",
            "  end of what finally arrives. Correct waiting and a hang look identical from "
            "outside.",
            "",
            "  THE WAIT IS NOT THE PROBLEM AND IS NOT WORTH SHORTENING. `check.yml` takes "
            "four to",
            "  five minutes, measured across 12 consecutive runs on 2026-09-20, and the "
            "claim commit's",
            "  checks are what a merge is waiting for. Five to ten minutes is the job "
            "working.",
            "",
            "  Run it so its output reaches you as it happens: nothing after it — no pipe, "
            "no redirect,",
            "  no filter. Read the heartbeat. It says which checks are still running and "
            "how long it",
            "  has been.",
            "",
            "  If you truly need a copy on disk afterwards, `tee` keeps every byte and is "
            "not refused",
            "  here — but it buffers too, so the heartbeat still will not reach you while "
            "it waits.",
        ], "BLOCKED: this would hide the heartbeat of a command that waits for minutes."))
    return Verdict(refusals, [])


# ------------------------------------------------------------------------------ the verdict

def read_command(command: str, cwd: str, backgrounded: bool = False) -> Verdict:
    """Every refusal this command earns, and every note about what could not be read.

    THE DEFAULT IS "NO OPINION", and it returns as early as it can: this runs on every Bash
    call in the session, and the overwhelming majority of them name none of these commands.
    """
    if shell_parse is None:
        return Verdict([], ["scripts/shell_parse.py could not be imported, so this guard has "
                            "no opinion about anything"])
    # A BACKGROUNDED COMMAND IS NEVER SKIPPED, and that is not caution — it is the fifth
    # clause's whole subject. `bash scratchpad/autodrive.sh` names none of these words: the
    # `while`/`sleep` was in the FILE, and the early return read the command as uninteresting
    # and let the four-hour runaway through. Measured as a failing case in the self-test
    # before this line existed.
    if not detached(command, backgrounded) and not any(word in command for word in
                                ("git", "gh ", "ln ", "tee", "while", "until", ">", "cd",
                                 "merge")):
        return Verdict([], [])

    reading = shell_parse.read(command)
    if not reading.placed:
        return Verdict([], [])

    refusals: List[Refusal] = []
    notes: List[str] = []
    root = checkout_root(cwd)
    for clause, verdict in (
        ("checkout", lambda: clause_checkout(reading, cwd)),
        ("tree", lambda: clause_tree_bash(reading, cwd, root)),
        ("gh", lambda: clause_gh(reading)),
        ("link", lambda: clause_link(reading, cwd)),
        ("wait", lambda: clause_wait(reading, command, cwd, backgrounded)),
        ("push", lambda: clause_push(reading, cwd)),
        ("stash", lambda: clause_stash(reading, cwd)),
        ("reset", lambda: clause_reset(reading, cwd)),
        ("narrate", lambda: clause_narrate(reading)),
    ):
        if _off(clause, command):
            continue
        got = verdict()
        refusals.extend(got.refusals)
        notes.extend(got.notes)
    return Verdict(refusals, notes)


def read_write(file_path: str, cwd: str) -> Verdict:
    if shell_parse is None or _off("tree", ""):
        return Verdict([], [])
    return clause_tree_write(file_path, cwd, checkout_root(cwd))


def render(refusals: Sequence[Refusal]) -> str:
    lines: List[str] = []
    for index, refusal in enumerate(refusals):
        if index:
            lines.append("")
        lines.append(refusal.heading)
        lines.extend(refusal.lines)
        lines.append("")
        lines.append("  {0}=off runs the command anyway.".format(HATCH[refusal.clause]))
    return "\n".join(lines)


def hook(payload: dict) -> int:
    """The PreToolUse hook. Exit 2 blocks the call and hands stderr to the session.

    IT FAILS OPEN ON ITS OWN BUGS. `reap.py:hook`'s docstring is the contract and it is not
    negotiable here: a guard that blocks every shell command when its parser throws is a
    guard somebody switches off inside a day, and a switched-off guard protects nothing.
    """
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    cwd = str(payload.get("cwd") or "") or os.getcwd()
    command = str(tool_input.get("command") or "")
    if command:
        verdict = read_command(command, cwd, bool(tool_input.get("run_in_background")))
    else:
        target = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        if not target:
            return 0
        verdict = read_write(target, cwd)
    if verdict.refusals:
        print(render(verdict.refusals), file=sys.stderr)
        return 2
    for note in verdict.notes:
        print("guard-shell: {0}".format(note), file=sys.stderr)
    return 0


def explain(command: str, write: str, cwd: str) -> int:
    verdict = read_write(write, cwd) if write else read_command(command, cwd)
    for note in verdict.notes:
        print("no opinion: {0}".format(note))
    if not verdict.refusals:
        print("ALLOWED  {0}".format(shell_parse.short((command or write).replace("\n", " "))
                                    if shell_parse else (command or write)))
        return 0
    print(render(verdict.refusals))
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guard-shell",
        description="Refuse nine shell mistakes this repo has already paid for.",
    )
    parser.add_argument("--hook", action="store_true",
                        help="run as a PreToolUse hook; reads the payload on stdin")
    parser.add_argument("--explain", metavar="CMD", default="",
                        help="the verdict for one command, and why")
    parser.add_argument("--explain-write", metavar="PATH", default="",
                        help="the verdict for one write target")
    parser.add_argument("--clauses", action="store_true",
                        help="the clause table: name, rule, escape hatch")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.clauses:
        for clause in CLAUSES:
            print("{0:<10} {1:<22} {2}".format(clause.name, clause.hatch + "=off", clause.rule))
        return 0
    if args.hook:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            return 0
        if not isinstance(payload, dict):
            return 0
        return hook(payload)
    if args.explain or args.explain_write:
        return explain(args.explain, args.explain_write, os.getcwd())
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 — the fail-open floor; see the module docstring
        # A HOOK THAT CRASHES MUST NOT BLOCK A SHELL. A broken guard that exits 0 protects
        # nothing, which is strictly better than a broken guard that stops the session from
        # working and gets removed.
        if "--hook" in sys.argv:
            sys.exit(0)
        raise
