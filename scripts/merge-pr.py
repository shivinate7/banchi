#!/usr/bin/env python3
"""`make merge` — merge a pull request, then move this clone's main onto it.

D42 settles that a session performs BOTH HALVES on the owner's word and does not stop in
between to ask again: `gh pr merge`, then the local fast-forward. This is that operation, with
the half nobody can remember done by a machine.

WHAT GOES WRONG IS NEVER THE DECISION. The local half has two correct forms and the choice
between them is a STATE LOOKUP, not a judgement:

    main checked out in no worktree     git fetch origin && git fetch origin main:main
    main checked out at <path>          git -C <path> pull --ff-only

Run the second when main is not actually the branch in that tree and it does not error. It
fast-forwards WHATEVER BRANCH THAT TREE IS STANDING ON, moves no protected ref, and so trips
no hook — the only symptom is a branch somebody else is working on having quietly advanced.
D42 names it as the footgun and leaves it to a session to remember; this asks git instead.

WHY THIS DOES NOT REOPEN D42'S REJECTION. That entry rejected "a `make` target that picks for
you", on the grounds that it would delete the choice and read as routine plumbing. The choice
it meant is WHETHER TO MERGE, and that is untouched: this refuses without a PR number somebody
typed and a `--confirm` somebody added, and a bare invocation is a free preview that presses
nothing — D33's instrument one register down. What is automated is the lookup, which nobody
makes deliberately and which is silent when wrong. See D42's own amendment.

IT NEVER SETS `PKMNSCAN_MAIN`, and no refusal here suggests it. D42 is explicit that a session
typing that variable has left the amendment behind. This works because allow rule 3 of
`scripts/githooks/reference-transaction` ALREADY permits a move to a commit origin carries;
the job here is to ESTABLISH that precondition — fetch first, then assert ancestry — so the
hook is never asked to refuse. The two fetches are two transactions in that order for the
reason D42 measured: the combined refspec moves both refs at once, and the hook would then be
judging `new` against the `origin/main` the same transaction is about to replace.

THE LOCAL HALF IS DRIVEN BY A TEST. `--local <rev>` runs it alone against whatever repository
the working directory is in, which is how `scripts/merge-selftest.sh` exercises every branch
of it — including the footgun — in a throwaway origin, clone and worktree. Nothing here
resolves paths relative to this file: the repository is the one `git rev-parse` answers for
from the caller's directory, so the self-test can point it at a temporary one.

AND IT IS BRACKETED BY TWO GUARDS OVER ITSELF, because `make merge` runs the merge script of
whatever checkout invoked it and this machine carries around twenty-seven of them. Before
anything is pressed, `surface_half` refuses a copy of this file that is BEHIND origin/main's;
after main has moved, `landed_half` asks what main now carries. The first refuses a known
cause, the second catches the symptom whatever caused it. Both sections carry the argument.

    scripts/merge-pr.py <n>                  preview. Presses nothing.
    scripts/merge-pr.py <n> --confirm        merge it, then move main.
    scripts/merge-pr.py --local <rev>        the local half alone, for the self-test.
    scripts/merge-pr.py --cut <branch>       the branch cleanup alone, for the self-test.
    scripts/merge-pr.py --surface            is this copy of the merge current with main?
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, NamedTuple, Optional, Sequence, Tuple

# THE RIG'S OWN SYNC, IMPORTED FROM THIS CHECKOUT'S `scripts/`. `surface_half` above is the
# reason to say where from: `make merge` runs the merge script of whatever tree invoked it, and
# 24 of 30 trees were behind main's copy of this file on the day that guard was written. The
# sync it calls is therefore this tree's too, and `--surface` already reports when that is
# stale.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import primary_sync  # noqa: E402

WIDTH = 76


class Ran(NamedTuple):
    ok: bool
    out: str
    err: str
    # THE CODE, AND NOT ONLY WHETHER IT WAS ZERO. One caller below needs to tell an answer of
    # `there is an unclaimed id` from `I could not be asked` — 3 from 2 — and a boolean cannot.
    # It carries -1 when the process never ran, which is neither.
    code: int = -1


def run(args: Sequence[str], cwd: Optional[str] = None) -> Ran:
    """A subprocess, never a shell. Failure is a value here, not an exception.

    Every refusal in this file wants the command's own stderr in the message — a hook's
    refusal names itself, and git's own refusal names a path, and D42 spends a paragraph on
    telling those two apart. Swallowing either would leave a session guessing which it hit.
    """
    try:
        done = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, check=False)
    except OSError as exc:
        return Ran(False, "", str(exc))
    return Ran(done.returncode == 0, done.stdout.strip(), done.stderr.strip(), done.returncode)


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


# ------------------------------------------------------------------- reading the clone


def repo_root(cwd: Optional[str] = None) -> Optional[str]:
    got = run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    return got.out or None


def main_worktrees(root: str) -> List[str]:
    """Every working tree with refs/heads/main checked out. D42's own question, in Python.

    Git allows a branch in at most one worktree, so this is a list of nought or one — but it
    is READ as a list rather than asserted to be one, because the whole point of this function
    is that the answer is not assumed.
    """
    got = run(["git", "worktree", "list", "--porcelain"], cwd=root)
    if not got.ok:
        return []
    found, here = [], None
    for line in got.out.splitlines():
        if line.startswith("worktree "):
            here = line[len("worktree "):].strip()
        elif line.strip() == "branch refs/heads/main" and here:
            found.append(here)
    return found


def worktree_holding(root: str, branch: str) -> Optional[str]:
    """The working tree with `branch` checked out, or None. main_worktrees generalised.

    This exists because deleting a merged branch is only safe when nobody is standing on it,
    and this clone runs several worktrees. Git allows a branch in at most one, so the answer
    is one path or none.
    """
    got = run(["git", "worktree", "list", "--porcelain"], cwd=root)
    if not got.ok:
        return None
    here = None
    for line in got.out.splitlines():
        if line.startswith("worktree "):
            here = line[len("worktree "):].strip()
        elif line.strip() == "branch refs/heads/{0}".format(branch) and here:
            return here
    return None


def head_of(root: str, ref: str) -> str:
    return run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=root).out


# ----------------------------------------------- is THIS copy of the merge current with main?

# `make merge` RUNS THE MERGE SCRIPT OF WHATEVER CHECKOUT INVOKED IT, and that is not a
# detail — it is the delivery mechanism for every defect this file has ever fixed. There are
# around twenty-seven working trees on this machine and many stand on branches cut before the
# capability whose absence they will demonstrate. A copy that lacks one does not fail: it
# performs the merge, moves main, reports complete success, and the capability simply does not
# happen.
#
# IT HAS HAPPENED TWICE, WITH THE SAME CAPABILITY AND IN SILENCE BOTH TIMES. D140 made an id
# claimed at the merge, by a function in THIS file. Run from a checkout older than that
# function, the merge did both halves and main landed carrying a raw `## D-<slug>` heading
# that no citation can resolve against and no later claim can ever find — once on 2026-09-11
# and once in the days before it, each repaired afterwards by a pull request of its own.
#
# THE PREDICATE IS `BEHIND`, AND `DIFFERS` WOULD BE THE WRONG ONE. A branch developing this
# file is SUPPOSED to differ from main — the pull request that wrote the paragraph above did
# exactly that — so comparing content would refuse the one workflow that keeps this file
# alive. What is refused is a copy MISSING commits main has: `git log HEAD..origin/main -- <f>`
# non-empty, which is true of a stale checkout and false of one that is ahead. A branch that
# has both changed the file and not yet taken main's change to it reads as behind, and that is
# correct rather than harsh — it lacks the capability exactly as the stale checkout does, and
# the repair is the same one sentence.
#
# WHAT IT CANNOT SEE, named rather than left to be discovered: a merge that took `ours` for
# one of these files. That commit IS an ancestor, so the reachability question answers `not
# behind` over content that lost the capability anyway. `make revert-guard` is the guard whose
# subject that is, and `--landed` below is what catches the consequence regardless of cause.
#
# AND THERE IS NO ESCAPE HATCH, WHICH IS A DEPARTURE FROM EVERY OTHER REFUSAL IN THIS REPO
# AND IS MEANT. `PKMNSCAN_SUITE_LOCK=off` and `PKMNSCAN_KILL=off` exist because the thing they
# bypass can cost real minutes or stand between a session and the only way through. This one
# costs `git merge origin/main`, which is seconds and is the right thing to have done anyway.
# A hatch printed in the refusal is the button a session presses instead of reading, and the
# defect it would re-create is one that reports success while doing nothing.

# The file's own TRACKED path, not `__file__`. The self-test points a real script at a
# throwaway repository, where `__file__` resolves outside the tree entirely.
SELF = "scripts/merge-pr.py"
# A module-level constant naming a script under `scripts/`. That is how this file already
# declares the one thing it shells out to, so the surface is DERIVED from the source rather
# than listed beside it and a capability moved into a new script joins it by being written the
# way the existing one is.
_SHELLED_OUT = re.compile(r"^[A-Z][A-Z0-9_]* = \"(scripts/[^\"]+\.py)\"", re.M)


def merge_surface() -> List[str]:
    """The files `make merge` EXECUTES, this one included, in a stable order."""
    try:
        with open(__file__, encoding="utf-8") as handle:
            source = handle.read()
    except OSError:
        source = ""
    return sorted({SELF} | set(_SHELLED_OUT.findall(source)))


def behind_on(root: str, path: str, ref: str) -> List[str]:
    """`<short> <subject>` for every commit on `ref` that touched `path` and HEAD has not."""
    got = run(["git", "log", "--format=%h %s", "HEAD.." + ref, "--", path], cwd=root)
    return [line for line in got.out.splitlines() if line.strip()] if got.ok else []


def surface_half(root: str, ref: str = "refs/remotes/origin/main") -> int:
    """Refuse before anything is pressed when this checkout's merge is behind main's."""
    rule("the merge this checkout is running")

    fetched = run(["git", "fetch", "origin"], cwd=root)
    if not fetched.ok:
        return refuse(
            "`git fetch origin` failed, so nothing can be said about whether this",
            "checkout's own copy of the merge is current.",
            "",
            fetched.err or "(git said nothing)",
            "",
            "Nothing was merged. An answer this command has not got is not a pass — the",
            "same rule the claim commit's wait is built on.")

    if not head_of(root, ref):
        return refuse(
            "`{0}` cannot be read after a successful fetch.".format(ref),
            "",
            "This checkout's copy of the merge is compared against main's. Without main",
            "there is nothing to compare it to, and a merge performed by a copy nobody",
            "could check is exactly the shape of the defect this refusal exists for.")

    stale: List[Tuple[str, List[str]]] = []
    for path in merge_surface():
        missing = behind_on(root, path, ref)
        if missing:
            stale.append((path, missing))

    if not stale:
        say("  {0} file(s) make up `make merge`, and this checkout carries every".format(
            len(merge_surface())),
            "  commit origin/main has for each of them.")
        return 0

    lines = ["this checkout's copy of the merge is BEHIND origin/main."]
    for path, missing in stale:
        here = head_of(root, "HEAD:" + path)[:9] or "(absent)"
        theirs = head_of(root, ref + ":" + path)[:9] or "(absent)"
        lines += [
            "",
            "  {0}".format(path),
            "    here         {0}".format(here),
            "    origin/main  {0}".format(theirs),
            "    missing {0} commit(s) main has:".format(len(missing)),
        ]
        lines += ["      " + line for line in missing[:6]]
        if len(missing) > 6:
            lines.append("      … and {0} more".format(len(missing) - 6))
    lines += [
        "",
        "  `make merge` runs THIS checkout's copy of these files, so a capability main has",
        "  added to them is one this merge would not perform. It would not fail either: it",
        "  would do both halves, report success, and leave the work undone. An unclaimed id",
        "  reached main that way twice.",
        "",
        "  BEING AHEAD IS NOT THIS. A branch developing the merge itself carries main's",
        "  commits plus its own and goes straight through; what is refused is a copy that is",
        "  MISSING commits main has.",
        "",
        "  Nothing was merged and main has NOT moved. Either one fixes it:",
        "",
        "    git -C {0} merge origin/main".format(root),
        "    run `make merge` from a checkout cut from main as it stands now",
    ]
    return refuse(*lines)


# ---------------------------------------------------- and what main carries once it has moved


def landed_half(root: str, commit: str) -> int:
    """After the move: does main carry an unclaimed id? 0 when clean, 1 when not or unknown.

    THIS IS THE SYMPTOM, CAUGHT BY THE SYMPTOM, and it is deliberately not the same guard as
    the one above. That one refuses a known cause before the damage; this one asks the only
    question that matters afterwards, and answers it the same way whether the claim was
    skipped by a stale checkout, by `--no-claim`, by a merge that took `ours` over the claimer,
    or by a slug written somewhere the claimer does not walk.
    """
    rule("what main now carries")
    asked = run([sys.executable, CLAIMER, "--landed", commit, "--root", root], cwd=root)
    if asked.code == 0:
        say("  no unclaimed id on {0} — every heading it carries is a number.".format(
            commit[:9]))
        return 0

    say("")
    if asked.code == 3:
        say(asked.out.rstrip() or asked.err.rstrip())
        say("",
            "  THE MERGE ITSELF COMPLETED and main has moved: this status is the report,",
            "  not a failure of the operation. Nothing here repairs it, because a",
            "  substitution made now would land on main's own copy of the entry (D140).")
        return 1

    say("REFUSED: main moved and this checkout could not be asked what it carries.",
        "",
        "  " + (asked.err or asked.out or "(the claimer said nothing)").splitlines()[-1],
        "",
        "  The merge completed. An answer this command has not got is not a pass, so this",
        "  is reported rather than assumed clean: read",
        "  `python3 scripts/claim-ids.py --landed {0}` yourself.".format(commit[:9]))
    return 1


# ------------------------------------------------------------------------- the local half


def local_plan(root: str, commit: str) -> Tuple[Optional[List[str]], Optional[str], str]:
    """(the command that moves main, the tree it runs in, why this form).

    Split out from the running so the preview and the act cannot disagree about what would
    happen — the preview prints exactly the list this returns.
    """
    holders = main_worktrees(root)
    if not holders:
        return (
            ["git", "fetch", "origin", "main:main"],
            root,
            "main is checked out in no worktree, so there is nowhere to switch to and the "
            "refspec form is the one that applies.",
        )
    if len(holders) > 1:
        return None, None, (
            "git reports main checked out in more than one worktree, which it does not "
            "permit: " + ", ".join(holders)
        )
    return (
        ["git", "pull", "--ff-only"],
        holders[0],
        "main is checked out at {0}, and `git fetch origin main:main` is exactly what git "
        "refuses against a branch somebody is standing on. That refusal would be git's and "
        "not a hook's.".format(holders[0]),
    )


def primary_half(root: str, confirm: bool) -> int:
    """AND THE RIG ITSELF, PUT BACK ON MAIN (D-the-primary-checkout-syncs-itself).

    THE HOLE THIS FILLS IS `local_plan`'S FIRST BRANCH. When main is checked out in no worktree
    — the ordinary state of this clone, with ~30 worktrees on feature branches — the refspec
    form moves `refs/heads/main` and stands in no tree at all. So the merge completes, main is
    current, and the PRIMARY checkout is still parked on whatever branch it was on: the exact
    state D139 and D158 were both written about, arrived at by the command that is supposed to
    leave everything tidy.

    THE COORDINATOR HAD BEEN DOING THIS BY HAND ALL NIGHT, with a driver script that dies with
    the session. That is the argument for it living here: `make merge` is the one moment this
    repository already knows main has moved.

    IT IS ITS OWN HALF AND NOT PART OF `local_half`, because it can fail without the merge
    having failed. The GitHub half is done, main is on origin, and a rig that would not sync
    because somebody has uncommitted work in it is not a broken merge — it is a message. So
    this never changes the exit status of the merge.
    """
    rule("the rig")
    verdict = primary_sync.sync(Path(root), confirm=confirm)
    if verdict.action == primary_sync.NOT_SUBJECT:
        # Silent by design in `primary_sync`; said once here, because `make merge` prints a
        # section per half and an empty section reads as a step that was skipped by accident.
        say("  nothing to do — see `python3 scripts/primary_sync.py --json` for which reason.")
        return 0
    for line in verdict.lines:
        say("  " + line if not line.startswith("primary-sync:") else line)
    # NEVER NON-ZERO. A refusal here is information about the rig and not a failed merge, and
    # returning 1 would make `make merge` report an incomplete operation for something that
    # completed.
    return 0


def local_half(root: str, commit: str, confirm: bool) -> int:
    """Fetch, prove the precondition, then move main — or say precisely why not."""
    rule("the local half")

    fetched = run(["git", "fetch", "origin"], cwd=root)
    if not fetched.ok:
        return refuse(
            "`git fetch origin` failed, so nothing can be proved about origin/main.",
            fetched.err or "(git said nothing)",
        )
    say("  fetched origin. origin/main is {0}".format(
        head_of(root, "refs/remotes/origin/main")[:9] or "unknown"))

    # THE WHOLE SAFETY ARGUMENT IS THIS ONE PREDICATE, and it is deliberately the same one
    # scripts/githooks/reference-transaction evaluates at `prepared`. Checked here, before
    # anything moves, so a wrong commit is refused by name rather than by a hook whose message
    # is written for a different mistake.
    ancestor = run(
        ["git", "merge-base", "--is-ancestor", commit, "refs/remotes/origin/main"], cwd=root
    )
    if not ancestor.ok:
        return refuse(
            "{0} is not on origin/main.".format(commit[:9]),
            "",
            "main only ever moves to a commit origin already carries — that is allow rule 3",
            "of scripts/githooks/reference-transaction, and this checks it rather than",
            "letting the hook discover it. A commit that is not there is a local commit, a",
            "local merge or a branch that was never merged.",
            "",
            "Nothing was moved.",
        )
    say("  {0} is on origin/main — the move the ref hook permits.".format(commit[:9]))

    command, tree, why = local_plan(root, commit)
    if command is None:
        return refuse(why)
    say("", "  " + why)

    # Belt and braces over the footgun. `local_plan` chose the pull form BECAUSE main is the
    # branch there; asking again costs one command and is the difference between advancing
    # main and silently advancing somebody's feature branch.
    if command[1] == "pull":
        on = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=tree).out
        if on != "main":
            return refuse(
                "{0} reports HEAD on `{1}`, not main.".format(tree, on or "an unreadable ref"),
                "",
                "`git pull --ff-only` there would fast-forward THAT branch. It moves no",
                "protected ref, so no hook has anything to say, and the only symptom is a",
                "branch somebody else is working on having quietly advanced.",
                "",
                "Nothing was moved.",
            )
        dirty = run(["git", "status", "--porcelain"], cwd=tree)
        if dirty.out:
            return refuse(
                "{0} has uncommitted changes, so the fast-forward is not safe.".format(tree),
                "",
                *["  " + line for line in dirty.out.splitlines()[:10]],
                "",
                "Reported rather than forced: what is in that tree is not this command's to",
                "discard. The GitHub half is done; finish the local half by hand there.",
            )

    before = head_of(root, "refs/heads/main")
    say("", "  would run:  {0}".format(" ".join(command)),
        "  in:         {0}".format(tree),
        "  main is at: {0}".format(before[:9] or "(no main in this clone)"))

    if not confirm:
        say("", "  PREVIEW — nothing was run. Add --confirm to perform it.")
        return 0

    moved = run(command, cwd=tree)
    after = head_of(root, "refs/heads/main")
    if not moved.ok:
        return refuse(
            "the local half did not complete. THE GITHUB HALF MAY ALREADY BE DONE.",
            "",
            moved.err or moved.out or "(git said nothing)",
            "",
            "This is an INCOMPLETE OPERATION, not a missing permission (D42): the word was",
            "given and the first half acted on it. Re-running this command is safe — an",
            "already-merged PR is detected and only the local half is retried.",
        )
    say("  main:       {0} -> {1}".format(before[:9] or "(none)", after[:9]))
    if after == before:
        say("  (already there — nothing to fast-forward)")
    return 0


# ------------------------------------------------------------------------ the GitHub half


# ------------------------------------------------------- the ids this branch has not claimed

# THE NUMBER IS ALLOCATED HERE AND NOWHERE EARLIER (D140). A branch writes
# its entry's heading as a slug because the allocation's only input — what main has taken — is not knowable
# until this moment. Thirteen renumber events are in D72 and every one of them is a branch
# having guessed; `origin/main` took two decision numbers and two build steps DURING the
# session that built this, which is the race happening while it was being written about.
#
# BEFORE THE MERGE, AND THE WAIT IS THE POINT. The substitution is committed to the PULL
# REQUEST's branch and its checks are watched to completion, so nothing main has never run CI
# over reaches main. The owner chose this against claiming by an explicit press earlier (which
# leaves a race, narrow but real) and against claiming on main afterwards (which puts an
# unverified substitution on the protected branch, recoverable only by another pull request).
# It costs one CI run per merge, paid once per entry rather than once per collision.
#
# IT REFUSES RATHER THAN GUESSING WHICH TREE. The claim is a commit and a push, so this
# checkout has to be standing on the PR's own head branch; a `make merge` run from main or
# from another worktree would otherwise commit the substitution onto whatever is checked out.

CLAIMER = "scripts/claim-ids.py"


# AND THE CLAIM HAS A SECOND HALF, WHICH IS NOT ABOUT SLUGS (D140, amended 2026-09-11). Once
# a branch has claimed there is no slug left, so `claims_pending` is empty and the claim half
# used to say `nothing to claim` and wave the merge through. The number it allocated can be
# taken by main in the meantime, and nothing looked again: on 2026-09-11 that happened TWICE
# in one evening — #262 and #265 on one id, #265 and #270 on the next — and a person reading
# PR titles was the only thing that caught either.
#
# IT RUNS BEFORE THE PENDING CHECK AND IN PREVIEW TOO, because a preview whose whole job is to
# say what the merge would do must say this. `decision index` is the backstop and stays; it
# fails the second branch's own COMMIT, after the collision is written. This is the earlier,
# cheaper warning, and `make merge` is where it is worth the most — the fetch immediately
# above it is what makes the answer current.


def stale_claim(root: str, ref: str = "origin/main") -> Optional[str]:
    """The staleness report, or None when every id this branch adds is still free on `ref`."""
    got = run([sys.executable, CLAIMER, "--stale", "--ref", ref, "--root", root], cwd=root)
    return None if got.ok else (got.out or got.err).rstrip()


def claims_pending(root: str, ref: str = "origin/main") -> List[str]:
    """`slug -> number` lines for every unclaimed id, or [] when there are none."""
    got = run([sys.executable, CLAIMER, "--porcelain", "--ref", ref, "--root", root], cwd=root)
    return [line for line in got.out.splitlines() if line.strip()] if got.ok else []


# ------------------------------------------------------- the wait, and what it is a wait FOR

# THE SUBJECT IS THE COMMIT, AND ASKING ABOUT THE PULL REQUEST IS NOT A NEAR MISS.
# `gh pr checks <n>` answers about a PULL REQUEST. Immediately after the claim commit is
# pushed, GitHub has not attached any check run to the new head yet, so that question is
# answered out of the PREVIOUS head's runs — complete, green, and about a tree that does not
# carry the substitution. The command exits 0 at once and the wait D140 sells is not bought.
# THE FASTER THE PUSH-TO-WATCH GAP, THE MORE RELIABLY IT READS THE WRONG COMMIT, and it has
# to see the old head GREEN to be silent, which is why nothing noticed for as long as the
# heads were green. Measured on two live merges the same evening:
#
#   PR #275   every job URL the merge printed belonged to run 34655700236, which is the
#             PRE-CLAIM commit's. The claim commit had its own run, 34655942932, and that
#             run was still `in_progress` when the merge fired.
#   PR #277   read the instant the merge returned, pinned to the claim commit: four of its
#             seven checks — all three design-check shards and `check` — were `in_progress`.
#
# Both trees later went green. That is a coin landing right, not a guard working.
#
# AND PINNING TO THE SHA IS NOT ENOUGH, WHICH IS THE WORSE HALF. A commit GitHub has not
# dispatched anything for yet answers with an EMPTY list, and "nothing is pending" read off
# an empty list is the same sentence as "everything passed". A watcher on #277 did exactly
# that the same evening — empty answer, zero pending, reported SETTLED — which would have
# merged a commit carrying no checks at all. So absence means ASK AGAIN here, never pass:
# a reading is conclusive only when it is non-empty, complete, at least as large as the one
# the parent commit carried, and unchanged across CHECK_SETTLE_READS consecutive reads.
#
# THE FLOOR IS THE PARENT'S COUNT BECAUSE IT IS THE ONLY LOWER BOUND THAT IS FREE. A claim
# commit's diff against main is a superset of its parent's — the claim only adds — and both
# gates this repo runs (`browser-scope`, D141, and `already-passed`, D136) only ever widen
# under a superset, so the parent's roster cannot be larger for a reason that is correct.
# Measured: #275's parent carried 6 runs and its claim commit 8, #277's parent 8 and its
# claim commit 8. It is a floor rather than an equality for exactly that first pair.
#
# EVERY WAY THIS CAN END EXCEPT ONE IS A REFUSAL, and that is deliberate. A read that fails,
# a roster that never fills, a deadline that arrives — none of them is evidence that the
# tree is green, and D140's whole bargain is that main takes nothing no CI run has seen.
#
# THIS IS NOT THE ONLY GUARD, SINCE 2026-09-12, AND IT IS NOT MADE REDUNDANT BY THE OTHER.
# GitHub's required status checks cover `check` and `revert-guard` server-side: a merge is
# refused while either is running AND while either is absent, so for those two contexts the
# race is closed at a layer no wrapper can be talked out of. What that gate does NOT cover is
# `design-check` — not required, and not requirable as the workflow stands, because the
# matrix reports `design-check (1..3)` when it runs and a bare `design-check` when
# `browser-scope` skips it, and the one fixed name in both shapes goes SKIPPED rather than
# FAILED when a shard is red. So the expensive half is this wait's alone. The other half is
# register: a refusal here names the check and the minutes, where the server gate names a
# merge state. See the entry above for the measurement and the finding.

# THE PAGE SIZE IS IN THE QUERY STRING AND NEVER IN A `-f`: gh switches the method to
# POST the moment a field is given, and this endpoint does not answer a POST at all.
CHECK_ENDPOINT = "repos/{owner}/{repo}/commits/%s/check-runs?per_page=100"
CHECK_POLL_SECONDS = 10
CHECK_SETTLE_READS = 2
CHECK_DEADLINE_SECONDS = 45 * 60
CHECK_HEARTBEAT_SECONDS = 60

# `skipped` and `neutral` are not failures — D141 skips the browser matrix by design and
# D136 skips a tree that has already passed, and both land here as completed check runs.
CHECK_FAILED = frozenset({
    "failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale",
})


class Reading(NamedTuple):
    """One answer about ONE COMMIT. `ok` is whether the question was answered at all.

    An unanswered question is not an empty answer, and the two are kept apart here rather
    than downstream: `Reading(False, (), err)` and `Reading(True, (), "")` both carry no
    runs, and only the second one is a fact about the commit.
    """

    ok: bool
    runs: Tuple[Tuple[str, str, str], ...]  # (name, status, conclusion), sorted
    err: str


def read_check_runs(sha: str) -> Reading:
    """Every check run GitHub has attached to `sha`, or why it could not be asked.

    `{owner}`/`{repo}` are gh's own placeholders and resolve from this checkout's remote,
    which is the same repository `gh pr checks` resolved against — so the repository is
    unchanged and only the SUBJECT moved.

    The runs are SORTED, because GitHub's ordering is not stable across reads and the settle
    below compares two readings for equality.
    """
    got = run(["gh", "api", CHECK_ENDPOINT % sha])
    if not got.ok:
        return Reading(False, (), got.err or got.out or "gh said nothing")
    try:
        body = json.loads(got.out)
    except ValueError as exc:
        return Reading(False, (), "gh api did not answer with JSON ({0})".format(exc))
    if not isinstance(body, dict):
        return Reading(False, (), "gh api answered with {0}, not an object".format(type(body).__name__))
    runs = tuple(sorted(
        (str(one.get("name") or "?"),
         str(one.get("status") or "?"),
         str(one.get("conclusion") or ""))
        for one in (body.get("check_runs") or [])
        if isinstance(one, dict)))
    return Reading(True, runs, "")


def attached_count(sha: str, read=None) -> int:
    """How many check runs `sha` carries, or 0 when that cannot be established.

    0 is the honest answer to an unreadable parent: it makes the floor inert and leaves the
    non-empty rule and the settle carrying the wait, which is a weaker guard and never a
    false one. A floor invented from a failed read would be the defect this file is fixing,
    rebuilt one function along.
    """
    got = (read or read_check_runs)(sha)
    return len(got.runs) if got.ok else 0


def _roster(runs: Sequence[Tuple[str, str, str]]) -> List[str]:
    return ["    {0:<12} {1}".format(status if status != "completed" else (conclusion or "?"), name)
            for name, status, conclusion in runs]


def wait_for_checks(sha: str, number: int, floor: int = 0,
                    read=None, sleep=None, now=None) -> Tuple[bool, List[str]]:
    """Poll ONE COMMIT's check runs until they are complete — or say why they never were.

    Returns (green, lines to print). Never raises, and never reports green off a reading it
    could not make, could not fill, or has not seen twice.
    """
    read = read or read_check_runs
    sleep = sleep or time.sleep
    now = now or time.monotonic

    started = now()
    spoke = started
    stable = 0
    seen: Optional[Tuple[Tuple[str, str, str], ...]] = None
    unreadable = ""

    while True:
        got = read(sha)

        if not got.ok:
            stable, seen = 0, None
            if got.err != unreadable:
                say("  the check runs could not be read: {0}".format(got.err))
                unreadable, spoke = got.err, now()
            waiting = "the check runs cannot be read"
        else:
            failed = [one for one in got.runs if one[2] in CHECK_FAILED]
            if failed:
                return False, ["  {0} of {1} check runs did not pass:".format(
                    len(failed), len(got.runs))] + _roster(got.runs)

            unreadable = ""
            if got.runs != seen:
                say("  {0} check run{1} attached to {2}:".format(
                    len(got.runs), "" if len(got.runs) == 1 else "s", sha[:9]))
                say(*_roster(got.runs))
                spoke = now()
            pending = [one for one in got.runs if one[1] != "completed"]

            if not got.runs:
                # ABSENCE IS NOT A PASS. Nothing is attached YET is what this reads as, and
                # the only other thing it could read as is the defect that made this rewrite.
                waiting, stable = "no check run is attached to this commit yet", 0
            elif pending:
                waiting, stable = "{0} of {1} still running".format(
                    len(pending), len(got.runs)), 0
            elif len(got.runs) < floor:
                waiting, stable = "{0} attached, and the parent commit carried {1}".format(
                    len(got.runs), floor), 0
            elif got.runs == seen:
                stable += 1
                waiting = "complete, and unchanged since the last read"
            else:
                stable = 1
                waiting = "complete; reading once more in case another arrives"
            seen = got.runs
            if stable >= CHECK_SETTLE_READS:
                return True, ["  all {0} check runs on {1} passed.".format(
                    len(got.runs), sha[:9])]

        spent = now() - started
        if spent >= CHECK_DEADLINE_SECONDS:
            return False, [
                "  gave up after {0:.0f} minutes: {1}.".format(spent / 60.0, waiting),
                "  PR #{0}'s claim commit is {1}.".format(number, sha),
            ]
        if now() - spoke >= CHECK_HEARTBEAT_SECONDS:
            say("  {0:.0f}m — {1}".format(spent / 60.0, waiting))
            spoke = now()
        sleep(CHECK_POLL_SECONDS)


def claim_half(root: str, number: int, branch: str, confirm: bool) -> int:
    """Allocate, commit, push, and wait for the claim commit's checks. 0 when clear.

    THE TREE IS ESTABLISHED BEFORE ANYTHING READS IT, and that ordering is the whole of
    D143. Both readers below — the staleness check and the pending check — ask
    their question of the CHECKED-OUT TREE. Neither can tell whether that tree is the pull
    request's, so a run pointed at the wrong one answers truthfully about the tree in front of
    it and uselessly about the merge it is performing.
    """
    here = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root).out.strip()
    if not branch:
        return refuse(
            "PR #{0} did not report a head branch, so there is no tree to check against."
            .format(number),
            "",
            "The claim reads the checked-out tree and has no way to know whether it is the",
            "pull request's. Without the branch name it cannot be told, and guessing is the",
            "one thing this path may not do.")
    if here != branch:
        return refuse(
            "this checkout is on `{0}`; PR #{1}'s branch is `{2}`.".format(here, number, branch),
            "",
            "The claim is a commit and a push onto that branch, so it has to be made from a",
            "tree standing on it. Run this from the worktree that holds it.",
            "",
            "THIS REFUSAL USED TO BE UNREACHABLE when the checked-out tree had nothing to",
            "claim. `main` has no slug in it, so a merge run from `main` read `main`, found",
            "nothing pending, reported `nothing to claim`, and merged the pull request's slug",
            "onto main verbatim. That happened on 2026-09-11 and `id claims` caught it.")

    run(["git", "fetch", "origin", "main"], cwd=root)

    gone_stale = stale_claim(root)
    if gone_stale is not None:
        rule("a claimed id has gone stale")
        say(gone_stale)
        return refuse(
            "this branch holds an id that `origin/main` has taken since it was claimed.",
            "",
            "Nothing has been merged and main has NOT moved. The claimer reports and never",
            "repairs: an un-claim has to happen BEFORE the merge and never after, because",
            "once main is merged in, a substitution on that token reaches main's own copy of",
            "the entry too.",
            "",
            "Put the id back to its slug form on the branch, push, and run this again. The",
            "claim half then allocates it against main as it stands, which is the whole",
            "bargain D140 makes.")

    pending = claims_pending(root)
    if not pending:
        say("  no unclaimed id on this branch — nothing to claim,",
            "  and every id it adds is still free on `origin/main`.")
        return 0

    rule("the claim")
    for line in pending:
        say("  {0}".format(line.replace("\t", "  ->  ", 1)))

    dirty = run(["git", "status", "--porcelain"], cwd=root).out.strip()
    if dirty:
        return refuse(
            "the working tree is not clean, and the claim commits everything it rewrites.",
            "", "  " + "\n  ".join(dirty.splitlines()[:8]))

    if not confirm:
        say("", "  would rewrite those ids, commit to `{0}`, push, and wait for its".format(branch),
            "  checks before merging.",
            "", "  PREVIEW — nothing was run.")
        return 0

    wrote = run([sys.executable, CLAIMER, "--write", "--root", root], cwd=root)
    if not wrote.ok:
        return refuse("`{0} --write` failed.".format(CLAIMER), wrote.err or wrote.out)
    say(wrote.out.rstrip())

    message = "Claim the ids this branch left as slugs (D140)\n\n" + "\n".join(
        "  " + line.replace("\t", " -> ") for line in pending)
    run(["git", "add", "-A"], cwd=root)
    made = run(["git", "commit", "-m", message], cwd=root)
    if not made.ok:
        return refuse("the claim could not be committed.", made.err or made.out)
    pushed = run(["git", "push", "origin", "HEAD"], cwd=root)
    if not pushed.ok:
        return refuse("the claim commit could not be pushed to `{0}`.".format(branch),
                      pushed.err or pushed.out,
                      "", "The claim is committed here and main has NOT moved. Push it yourself,",
                      "then run this again — a second run finds no unclaimed id and skips.")

    sha = run(["git", "rev-parse", "HEAD"], cwd=root).out.strip()
    parent = run(["git", "rev-parse", "--verify", "--quiet", "HEAD^"], cwd=root).out.strip()
    if not sha:
        return refuse(
            "the claim commit was pushed and its SHA could not be read back.",
            "",
            "The wait is about that commit and about nothing else, so there is nothing safe",
            "to wait on. The claim is pushed and main has NOT moved; watch the pull request",
            "yourself and run this again once it is green.")

    rule("waiting for the claim commit's checks")
    say("  this is the wait D140 buys: main never takes a substitution",
        "  no CI run has seen. The subject is the COMMIT — {0} — and".format(sha[:9]),
        "  never the pull request, whose checks answer out of the PREVIOUS",
        "  head until GitHub attaches runs to this one.", "")
    floor = attached_count(parent) if parent else 0
    if floor:
        say("  its parent {0} carries {1} check runs, so fewer than that".format(parent[:9], floor),
            "  on this commit means GitHub is still attaching them.", "")

    green, lines = wait_for_checks(sha, number, floor)
    say(*lines)
    if not green:
        return refuse(
            "PR #{0}'s claim commit {1} is not green.".format(number, sha[:9]),
            "",
            "The claim is pushed and main has NOT moved. Fix the branch and run this again;",
            "a second run finds no unclaimed id and goes straight to the merge.",
            "",
            "A wait that ENDED WITHOUT AN ANSWER lands here too, and that is the point: an",
            "empty answer, an unreadable one and a deadline are all `not known yet`, and",
            "none of the three is evidence that anything passed.")
    return 0


def pr_state(number: int) -> Tuple[Optional[dict], str]:
    got = run([
        "gh", "pr", "view", str(number), "--json",
        "number,title,url,state,mergeable,mergeStateStatus,headRefName,mergeCommit",
    ])
    if not got.ok:
        return None, got.err or got.out or "gh said nothing"
    try:
        return json.loads(got.out), ""
    except ValueError as exc:
        return None, "gh --json is not JSON ({0})".format(exc)


def merge_commit_of(data: dict) -> str:
    commit = data.get("mergeCommit") or {}
    return str(commit.get("oid") or "") if isinstance(commit, dict) else ""


def github_half(number: int, confirm: bool) -> Tuple[Optional[str], int]:
    """(the merge commit, an exit code). Idempotent on a PR that is already merged."""
    rule("the GitHub half")
    data, why = pr_state(number)
    if data is None:
        return None, refuse("could not read PR #{0}.".format(number), why)

    say("  #{0}  {1}".format(data.get("number"), data.get("title")),
        "  {0}".format(data.get("url")),
        "  branch {0} · state {1} · mergeable {2}".format(
            data.get("headRefName"), data.get("state"), data.get("mergeable")))

    if data.get("state") == "MERGED":
        commit = merge_commit_of(data)
        if not commit:
            return None, refuse(
                "PR #{0} is MERGED and gh names no merge commit.".format(number),
                "Without one there is nothing to prove ancestry against.")
        say("  already merged at {0} — the GitHub half is done, the local half is not."
            .format(commit[:9]))
        return commit, 0

    if data.get("state") != "OPEN":
        return None, refuse(
            "PR #{0} is {1}, not OPEN.".format(number, data.get("state")),
            "Nothing here closes or reopens a pull request.")
    if data.get("mergeable") == "CONFLICTING":
        return None, refuse(
            "PR #{0} conflicts with its base and cannot be merged.".format(number))

    if not confirm:
        say("", "  would run:  gh pr merge {0} --merge".format(number),
            "  a merge commit, matching every merge in this repository's history.",
            "  then the head branch is deleted on origin, and here too unless a worktree",
            "  holds it — that check is what the old refusal to delete anything stood in for.")
        return None, 0

    merged = run(["gh", "pr", "merge", str(number), "--merge"])
    if not merged.ok:
        return None, refuse("`gh pr merge {0} --merge` failed.".format(number),
                            merged.err or merged.out or "(gh said nothing)")
    say("  merged.")

    data, why = pr_state(number)
    if data is None or data.get("state") != "MERGED":
        return None, refuse(
            "gh reports PR #{0} is not MERGED after merging it.".format(number),
            why or "state: {0}".format(data.get("state") if data else "unreadable"),
            "Refusing to move main on a claim its own source will not repeat.")
    commit = merge_commit_of(data)
    if not commit:
        return None, refuse("PR #{0} merged and gh names no merge commit.".format(number))
    say("  merge commit {0}".format(commit[:9]))
    return commit, 0


# --------------------------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="merge-pr",
        description="Merge a pull request and move this clone's main onto it (D42).",
    )
    parser.add_argument("pr", nargs="?", type=int, help="the pull request number")
    parser.add_argument("--confirm", action="store_true",
                        help="perform it. Without this, everything is a preview.")
    parser.add_argument("--cut", metavar="BRANCH",
                        help="run the branch cleanup alone against BRANCH, skipping gh. What "
                             "scripts/merge-selftest.sh drives.")
    parser.add_argument("--no-claim", action="store_true",
                        help="skip the id claim. What scripts/claim-selftest.py drives, and "
                             "the escape hatch for a merge whose claim was already pushed by "
                             "hand.")
    parser.add_argument("--local", metavar="REV",
                        help="run the local half alone against REV, skipping gh. What "
                             "scripts/merge-selftest.sh drives.")
    parser.add_argument("--surface", action="store_true",
                        help="ask whether THIS checkout's copy of the merge is behind "
                             "origin/main, and refuse if it is. Runs on its own before every "
                             "merge; this flag runs it alone, which is what "
                             "scripts/merge-selftest.sh drives.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    root = repo_root()
    if root is None:
        return refuse("not a git repository.")

    if args.surface:
        return surface_half(root)

    if args.cut:
        cut_branch(root, args.cut, args.confirm)
        return 0

    if args.local:
        commit = head_of(root, args.local)
        if not commit:
            return refuse("`{0}` does not name a commit in this repository.".format(args.local))
        code = local_half(root, commit, args.confirm)
        if code:
            return code
        return primary_half(root, args.confirm)

    if args.pr is None:
        return refuse(
            "no pull request named.",
            "",
            "There is no default PR and there will not be one. D42 makes the merge a",
            "deliberate act on the owner's word, and a command with a default has already",
            "chosen for them.",
            "",
            "  make merge ARGS=92               preview. Presses nothing.",
            "  make merge ARGS=\"92 --confirm\"    merge it, then move main.",
        )

    say("PKMNSCAN — merge PR #{0}{1}".format(args.pr, "" if args.confirm else "  (PREVIEW)"))
    rule()

    # FIRST, BEFORE EVEN THE PULL REQUEST IS READ, AND IN THE PREVIEW TOO. A preview whose
    # whole job is to say what the merge would do has to say when this copy of the merge would
    # not do all of it — and the answer costs one fetch, which every path here pays anyway.
    code = surface_half(root)
    if code:
        return code

    if not args.no_claim:
        data, why = pr_state(args.pr)
        if data is None:
            return refuse("could not read PR #{0}.".format(args.pr), why)
        if data.get("state") != "MERGED":
            code = claim_half(root, args.pr, str(data.get("headRefName") or ""), args.confirm)
            if code:
                return code
    commit, code = github_half(args.pr, args.confirm)
    if code:
        return code
    if commit is None:  # preview of an unmerged PR: no commit exists to reason about yet
        rule("the local half")
        _, tree, why = local_plan(root, "")
        say("  " + why,
            "",
            "  after the merge, main would move in: {0}".format(tree or "(undecidable)"),
            "",
            "  PREVIEW — nothing was run. Add --confirm to perform it.")
        # THE RIG IS PREVIEWED TOO, because a preview that under-reports what `--confirm` will
        # do is the one thing a preview must not be. `primary_sync` presses nothing without its
        # own `confirm`, which is the same flag.
        primary_half(root, args.confirm)
        delete_head_branch(root, args.pr, args.confirm)
        return 0
    code = local_half(root, commit, args.confirm)
    if code:
        return code
    # AFTER main HAS MOVED AND BEFORE THE TIDYING. `local_plan`'s refspec form moves
    # `refs/heads/main` while standing in no tree, so this is the moment the primary checkout is
    # current on paper and still parked on a branch on disk. Its status is deliberately not the
    # command's — see `primary_half`.
    primary_half(root, args.confirm)
    delete_head_branch(root, args.pr, args.confirm)
    # LAST, AND ITS STATUS IS THE COMMAND'S. The cleanup above runs first on purpose: a branch
    # left lying around because main landed wrong helps nobody, and the report below is about
    # main rather than about the branch.
    return landed_half(root, commit)


# ------------------------------------------------------------------- the branch afterwards


def delete_head_branch(root: str, number: int, confirm: bool) -> None:
    """Delete the merged PR's head branch — on origin always, here when nobody stands on it.

    THIS RAN NOWHERE UNTIL 2026-09-05, AND 125 MERGED PULL REQUESTS LEFT 125 BRANCHES BEHIND.
    `delete_branch_on_merge` is false on the repository and `gh pr merge` was called without
    `--delete-branch`, so neither side ever cleaned up: 85 branches on origin and 106 here, of
    which 81 and 98 were pure ancestors of main holding nothing main did not.

    IT IS NOT `gh pr merge --delete-branch`, and the difference is the reason this function
    exists rather than a flag. That flag deletes the local branch too, and to do it gh may
    switch the current working tree to the base branch — underneath a local half whose whole
    job is to decide which tree main moves in and how. A merge wrapper that moves the ground
    under its own second half is worse than one that leaves a branch lying around. So this
    runs AFTER the local half has finished and succeeded, and it asks git the same question
    D42's local half asks: who is standing where.

    THE ORIGINAL REFUSAL IS KEPT AS THE LOCAL RULE. `github_half` used to print "the branch
    is NOT deleted: live worktrees track branches in this clone", and that hazard is real —
    this clone runs linked worktrees and one of them may hold the branch just merged. The
    remote branch is checked out nowhere by definition, so it goes unconditionally; the local
    one goes only when `worktree_holding` says no tree has it AND it is an ancestor of main,
    which after a successful local half it is.

    Nothing here can fail the merge. The merge already happened and main already moved; a
    branch that outlives them is untidy, not wrong, so every failure below is reported and
    swallowed.
    """
    data, _ = pr_state(number)
    branch = (data or {}).get("headRefName")
    if not branch:
        say("  could not read the head branch name — nothing deleted.")
        return
    cut_branch(root, branch, confirm)


def cut_branch(root: str, branch: str, confirm: bool) -> None:
    """The decision half of delete_head_branch, with no `gh` in it.

    Split out for the reason `--local` is split out: the GitHub half is a shell-out to a
    service and cannot be tested here, so the part that can be is made reachable on its own.
    `--cut <branch>` is what scripts/merge-selftest.sh drives.
    """
    if not confirm:
        say("", "  would then delete branch {0} on origin,".format(branch),
            "  and here too unless a worktree holds it.")
        return

    rule("the branch afterwards")

    gone = run(["git", "push", "origin", "--delete", branch], cwd=root)
    if gone.ok:
        say("  origin/{0}: deleted.".format(branch))
    elif "remote ref does not exist" in (gone.err or "") + (gone.out or ""):
        # NOT A FAILURE, AND SAYING SO MATTERS. `delete_branch_on_merge` on the repository
        # deletes the head branch server-side the moment `gh pr merge` returns, so this push
        # finds nothing left to delete — on EVERY merge, once that setting is on. Reported as
        # an error it would read as a broken wrapper; the branch being gone is the outcome
        # this function wanted. Also covers a branch that was never pushed at all.
        say("  origin/{0}: already gone — nothing to delete.".format(branch))
    else:
        say("  origin/{0}: not deleted — {1}".format(branch, (
            (gone.err or gone.out or "git said nothing").strip().splitlines()[-1])))

    if not head_of(root, "refs/heads/" + branch):
        say("  {0}: not in this clone.".format(branch))
        return

    held = worktree_holding(root, branch)
    if held:
        # NOT A DEAD END, AND IT READ AS ONE FOR 37 BRANCHES. This condition is true by
        # construction whenever a session merges its own PR from its own worktree, so the local
        # delete is skipped exactly when it is wanted — and nothing here ever came back to ask
        # again. `make janitor` is what asks again: the branch is an ancestor of main and its
        # remote copy has just been deleted above, so the sweep reaps it the moment no tree
        # holds it. Nothing is recorded to make that happen; the sweep re-derives it (D111).
        say("  {0}: kept — checked out in {1}.".format(branch, held),
            "    `make janitor` takes it once that tree is gone.")
        return

    if not run(["git", "merge-base", "--is-ancestor", branch, "main"], cwd=root).ok:
        say("  {0}: kept — not an ancestor of main, so it holds commits main does not."
            .format(branch))
        return

    # -D, not -d, and the check above is why. `git branch -d` refuses a branch that is behind
    # its own upstream — "not yet merged to refs/remotes/origin/<branch>" — even when every
    # commit on it is already in main. That refusal fires here routinely: the remote branch was
    # just deleted, and a branch whose upstream is gone reads as unmerged. The ancestor test is
    # a STRONGER claim than the one -d makes, so it stands in for it rather than beside it.
    cut = run(["git", "branch", "-D", branch], cwd=root)
    say("  {0}: {1}".format(branch, "deleted" if cut.ok else "not deleted — " + (
        (cut.err or cut.out or "git said nothing").strip().splitlines()[-1])))


if __name__ == "__main__":
    sys.exit(main())
