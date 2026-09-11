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

    scripts/merge-pr.py <n>                  preview. Presses nothing.
    scripts/merge-pr.py <n> --confirm        merge it, then move main.
    scripts/merge-pr.py --local <rev>        the local half alone, for the self-test.
    scripts/merge-pr.py --cut <branch>       the branch cleanup alone, for the self-test.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import List, NamedTuple, Optional, Sequence, Tuple

WIDTH = 76


class Ran(NamedTuple):
    ok: bool
    out: str
    err: str


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
    return Ran(done.returncode == 0, done.stdout.strip(), done.stderr.strip())


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


def claims_pending(root: str, ref: str = "origin/main") -> List[str]:
    """`slug -> number` lines for every unclaimed id, or [] when there are none."""
    got = run([sys.executable, CLAIMER, "--porcelain", "--ref", ref, "--root", root], cwd=root)
    return [line for line in got.out.splitlines() if line.strip()] if got.ok else []


def claim_half(root: str, number: int, branch: str, confirm: bool) -> int:
    """Allocate, commit, push, and wait for the claim commit's checks. 0 when clear."""
    run(["git", "fetch", "origin", "main"], cwd=root)
    pending = claims_pending(root)
    if not pending:
        say("  no unclaimed id on this branch — nothing to claim.")
        return 0

    rule("the claim")
    for line in pending:
        say("  {0}".format(line.replace("\t", "  ->  ", 1)))

    here = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root).out.strip()
    if here != branch:
        return refuse(
            "this checkout is on `{0}`; PR #{1}'s branch is `{2}`.".format(here, number, branch),
            "",
            "The claim is a commit and a push onto that branch, so it has to be made from a",
            "tree standing on it. Run this from the worktree that holds it.")
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

    rule("waiting for the claim commit's checks")
    say("  this is the wait D140 buys: main never takes a substitution",
        "  no CI run has seen.", "")
    watched = run(["gh", "pr", "checks", str(number), "--watch", "--fail-fast"])
    say((watched.out or watched.err).rstrip())
    if not watched.ok:
        return refuse(
            "PR #{0}'s checks are not green after the claim.".format(number),
            "",
            "The claim is pushed and main has NOT moved. Fix the branch and run this again;",
            "a second run finds no unclaimed id and goes straight to the merge.")
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
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    root = repo_root()
    if root is None:
        return refuse("not a git repository.")

    if args.cut:
        cut_branch(root, args.cut, args.confirm)
        return 0

    if args.local:
        commit = head_of(root, args.local)
        if not commit:
            return refuse("`{0}` does not name a commit in this repository.".format(args.local))
        return local_half(root, commit, args.confirm)

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
        delete_head_branch(root, args.pr, args.confirm)
        return 0
    code = local_half(root, commit, args.confirm)
    if code == 0:
        delete_head_branch(root, args.pr, args.confirm)
    return code


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
