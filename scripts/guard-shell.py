#!/usr/bin/env python3
"""Refuse five shell mistakes this repo has already made and paid for.

EVERY CLAUSE HERE HAS AN INCIDENT BEHIND IT, and not one of them was a lapse of care: each
was a rule somebody had already written down, in a memory file or in CLAUDE.md, and then
broken by a session that had read it. That is not a reason to write the rule again; it is
what D171 rules a rule IS. A rule is read once, at the start, and then competes with the
work. So these five are mechanical.

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

THE STANDARD IS `scripts/reap.py:hook`'S AND IT IS NOT NEGOTIABLE HERE EITHER:

    a broken GUARD fails OPEN — any parse error, any bug here, an unreadable payload, a
                                missing `git`: exit 0 and refuse nothing
    an unreadable TARGET fails CLOSED — but only where "unreadable" is this file being right
                                that it does not know AND the harm is unrecoverable, which is
                                true of none of these five: every one of them RESOLVES its
                                subject, and a subject it cannot resolve is a command it has
                                no opinion about

RESOLUTION, NEVER SPELLING, wherever the question has a real answer. `git checkout main` and
`git checkout CLAUDE.md` are the same six characters of verb: the first is a branch and the
second destroys work, and only the filesystem and `git status` can say which. `ln -s a b` is
right on Monday and wrong on Tuesday depending on whether `b` exists. That is reap.py's whole
argument, applied to four more commands.

FALSE POSITIVES ARE THE ONLY WAY A GUARD LIKE THIS DIES, and it dies silently — the hatch
goes into a shell profile and nobody ever sees the refusal again. So every clause is narrow on
purpose, every legitimate shape this repo actually types is pinned as PASSING in
`scripts/guard-shell-selftest.sh`, and each is RUN there before it is scored, because a case
that is secretly a typo passes for the wrong reason.

FIVE CLAUSES, FIVE HATCHES, AND THAT IS DELIBERATE. One switch for the whole hook would mean
disarming the destructive-checkout clause in order to make a symlink, which is how a guard
stops being one. Each refusal prints only its own, each is honoured in the environment and
inline, and all five are documented in CLAUDE.md (`make docs-audit`'s `env names` row refuses
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
# DECLARED, because five clauses each with their own hatch is five names a reader has to be
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
           "never write outside the checkout this session is standing in"),
    Clause("gh", "PKMNSCAN_GH",
           "never pass -f/-F to `gh api` without naming the method"),
    Clause("link", "PKMNSCAN_LINK",
           "use `ln -sfn`, or test the path is absent, when linking"),
    Clause("wait", "PKMNSCAN_WAIT",
           "never poll in a loop — background the work and take its notification"),
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

    if source:
        return Restoring(paths, source,
                         "a source is named, so this WRITES a known version rather than "
                         "discarding an unknown one", [])

    resolved: List[str] = []
    unresolved: List[str] = []
    for token in paths:
        if token in (".", "./") or os.path.lexists(os.path.join(cwd, token)):
            resolved.append(token)
        elif _run(["git", "rev-parse", "--verify", "--quiet", token + "^{commit}"], cwd=cwd)[0]:
            continue                      # a branch or a commit: nothing on disk is touched
        else:
            unresolved.append(token)
    return Restoring(resolved, "", "", unresolved)


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
        lines.append("      Nothing names a source, so this restores from the index and "
                     "those changes are gone.")
        lines.extend([
            "",
            "  On 2026-09-06 `git checkout cli/cmd_reprice.py` put one mutation back and took",
            "  ~240 lines of that session's uncommitted work with it. Every other file "
            "survived,",
            "  which made it look at first like a smaller problem than it was.",
            "",
            "  Put a mutation back with a COPY, which cannot reach anything you did not copy:",
            "      sed -i.bak 's/OLD/NEW/' path/to/file.py     # run the check",
            "      mv path/to/file.py.bak path/to/file.py",
            "  and where sed cannot express the edit, `cp file file.bak` … `cp file.bak file`.",
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

def _write_targets(reading: "shell_parse.Reading") -> List[str]:
    """Every path this command would WRITE, as far as a parse can say.

    TWO POSITIONS AND A DECLARED GAP. A redirection target is unambiguous, and `tee`'s
    operands are its whole purpose. `cp`, `mv`, `install`, `rsync` and `sed -i` are NOT read
    here: their destination is positional and mixed in with patterns and flags, and a clause
    that guessed wrong would refuse an ordinary copy. The Write|Edit half of this clause needs
    no parsing at all, which is why it is the half that cannot be skirted, and
    D-five-shell-mistakes names this gap rather than leaving it to be discovered.
    """
    targets: List[str] = []
    for placed in reading.placed:
        stage = placed.stage
        for redirect in (stage.fd1, stage.fd2):
            if redirect.kind == shell_parse.FILE and redirect.path:
                targets.append(redirect.path)
        argv = shell_parse.strip_prefixes(stage.argv)
        if argv and (argv[0] == "tee" or argv[0].endswith("/tee")):
            targets.extend(word for word in argv[1:] if not word.startswith("-"))
    return targets


def _resolve_target(target: str, cwd: str) -> str:
    """A write target resolved without requiring it to exist yet."""
    path = target if os.path.isabs(target) else os.path.join(cwd, target)
    parent = _real(os.path.dirname(path) or cwd)
    return os.path.join(parent, os.path.basename(path))


def _outside(target: str, cwd: str, root: str) -> Optional[Tuple[str, str]]:
    """(resolved target, why it is outside) — or None when the write is in bounds."""
    if "$" in target or "*" in target or "?" in target:
        return None                        # unexpanded by this parse; no honest answer
    resolved = _resolve_target(target, cwd)
    if _under(resolved, root):
        return None
    if _sanctioned_outside(resolved):
        return None
    return resolved, ""


def _tree_refusal(resolved: str, root: str, how: str) -> Refusal:
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
    ], "BLOCKED: this would write outside the checkout this session is standing in.")


def clause_tree_bash(reading: "shell_parse.Reading", cwd: str, root: str) -> Verdict:
    if not root:
        return Verdict([], ["this guard could not resolve a checkout root for {0}, so it has "
                            "no opinion about where a write lands".format(cwd)])
    refusals: List[Refusal] = []
    for target in _write_targets(reading):
        verdict = _outside(target, cwd, root)
        if verdict:
            refusals.append(_tree_refusal(verdict[0], root, "`{0}`".format(target)))
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
                                ("git", "gh ", "ln ", "tee", "while", "until", ">")):
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
        description="Refuse five shell mistakes this repo has already paid for.",
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
