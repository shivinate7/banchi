#!/usr/bin/env python3
"""The primary checkout puts itself back on main, and fast-forwards it. Both parts.

THE RULING THIS FILE IS. Asked whether the primary checkout is mechanically kept on `main` at
`origin/main`, and offered a guard that only refuses, the owner answered: *"why can't both
parts sync, remember this is a one man show, it's just me working."* So this is not a warning
and not a refusal — it is the two git commands, run for them, at the three moments somebody
would otherwise have to remember to type them.

WHAT "BOTH PARTS" MEANS, because the two halves fail separately and each was a real state:

  part 1   the primary checkout stands on `main` rather than on a feature branch. The state
           D139 and D158 were both written about: that one directory found on
           `claude/env-key-rotation` with three live sessions in it, and on
           `claude/debts-citation-repair` — already merged as #282 — with four.
  part 2   `refs/heads/main` is at `refs/remotes/origin/main`. The state `make status` reported
           as `0 ahead of main, 70 behind it` for a day while nobody read it.

A tree can be wrong in either alone. Back on main and 70 behind is still a rig serving code
nobody is reading; current and parked on a branch is the incident above. Two parts, both
synced, or a refusal that names which one it could not do.

WHY THIS IS NOT A REPEAL OF D42, which is the entry a reader will reach for. D42 is *"main
moves by pull request"*, and the move this file makes is a fast-forward to a commit `origin`
already carries — which `scripts/githooks/reference-transaction` has permitted since the day it
was written, as its own allow rule 3. So this decides WHO RUNS AN ALREADY-PERMITTED MOVE, and
not which moves run. The argument is in the decision entry beside this file; the hook's lines
are quoted there rather than paraphrased.

THE FAST-FORWARD-ONLY PREDICATE IS OURS AND IS NOT THE HOOK'S. Rule 3 asks whether the
DESTINATION is on `origin/main`; ours is `origin/main` itself, so rule 3 is satisfied by
construction and would permit a move that threw local commits away. What stops that is the
separate test below — `refs/heads/main` must be an ancestor of `refs/remotes/origin/main` —
and it is the whole reason this file can be trusted with a ref D42 protects.

IT FAILS OPEN ON ITS OWN BUGS AND CLOSED ON A TARGET IT CANNOT READ, which is
`scripts/reap.py:hook`'s rule and its reason: *"a guard that blocks every shell command when
`lsof` is missing or its own parser throws is a guard somebody switches off inside a day."*
Here the two directions are:

  open    an unexpected exception anywhere in this file answers `not-subject`, SILENTLY.
          Three callers run this unasked — a SessionStart hook, a supervisor tick, a merge —
          and a bug in it must cost a sync that did not happen, never a session that will not
          start or a rig that will not come up.
  closed  a fact it needs and cannot read — HEAD, `refs/heads/main`, the worktree list, the
          status — is a refusal, and a LOUD one. Not knowing whether a tree is safe to move is
          not evidence that it is.

Both directions end in "nothing was moved". What differs is whether anybody is told, and the
difference is the whole of it: this file's own failure is not the operator's business, and its
inability to read their tree very much is.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(REPO_ROOT))
from server import ports  # noqa: E402

# The escape hatch, spelled the way `PKMNSCAN_MAIN=off`, `PKMNSCAN_KILL=off`,
# `PKMNSCAN_REVERT=off`, `PKMNSCAN_SUITE_LOCK=off` and `PKMNSCAN_SERVE_MAIN=off` already are.
#
# IT TURNS THE MECHANISM OFF RATHER THAN LETTING SOMETHING PAST, which is a departure from every
# other hatch in this repo and is worth saying. The others stand between a person and an act
# they mean; this one performs an act on their behalf, so what a reader wants from the hatch is
# not "do it anyway" but "stop doing it". That is why it is printed on every REFUSAL as well as
# on every sync: a refusal is the mechanism announcing itself, and the reader's next question is
# how to stop being asked.
SYNC_ENV = "PKMNSCAN_SYNC"

# What git leaves in the git dir while an operation is half-done. Any one of these means a
# person or a script is mid-something, and moving the branch under it is how a rebase becomes
# an afternoon.
#
# READ AS PATHS RATHER THAN ASKED OF `git status`, deliberately: `--porcelain` v1 says nothing
# about a rebase in progress at all, and the long form's wording is prose that has changed
# between gits. These four names have not.
MID_OPERATION = (
    ("MERGE_HEAD", "a merge is in progress"),
    ("CHERRY_PICK_HEAD", "a cherry-pick is in progress"),
    ("REVERT_HEAD", "a revert is in progress"),
    ("BISECT_LOG", "a bisect is in progress"),
    ("rebase-merge", "a rebase is in progress"),
    ("rebase-apply", "a rebase or an `am` is in progress"),
)

MAIN_REF = "refs/heads/main"
ORIGIN_MAIN_REF = "refs/remotes/origin/main"

# The four answers. `NOT_SUBJECT` prints nothing anywhere; the other three always print.
NOT_SUBJECT = "not-subject"
ALREADY = "already"
SYNCED = "synced"
REFUSED = "refused"


class Ran(NamedTuple):
    ok: bool
    out: str
    err: str


class Verdict(NamedTuple):
    """What happened, and the lines that say so.

    `lines` is the whole of what a caller prints — the one-line announcement first, any detail
    under it, the escape hatch last. Composed here rather than at three call sites, because
    three spellings of a refusal is three refusals to keep in step, and the hook's is in bash.
    """

    action: str
    lines: List[str]
    root: Optional[str] = None
    branch: Optional[str] = None       # the branch it was on, when that was not main
    before: Optional[str] = None       # refs/heads/main before
    after: Optional[str] = None        # refs/heads/main after
    behind: int = 0                    # commits main gained
    reason: Optional[str] = None       # a short machine token for the selftest and --json

    @property
    def moved(self) -> bool:
        return self.action == SYNCED

    def json(self) -> str:
        return json.dumps({
            "action": self.action,
            "root": self.root,
            "branch": self.branch,
            "before": self.before,
            "after": self.after,
            "behind": self.behind,
            "reason": self.reason,
            "lines": self.lines,
        }, indent=2)


def _git(root: Path, *argv: str, timeout: float = 30.0) -> Ran:
    """One git command, never raising.

    `PKMNSCAN_MAIN` IS NOT SET HERE AND MUST NOT BE. The fast-forward this file performs is one
    `scripts/githooks/reference-transaction` already permits, so it needs no hatch — and a
    module that quietly passed one would be telling the hook to stand aside for every move it
    makes, including the ones its own predicate was meant to catch. If the hook ever refuses
    this file's move, that is a finding and not a thing to route around.
    """
    try:
        done = subprocess.run(  # noqa: S603, S607
            ["git", *argv], cwd=str(root), capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return Ran(False, "", "git could not be run")
    return Ran(done.returncode == 0, (done.stdout or "").strip(), (done.stderr or "").strip())


# ------------------------------------------------------------------ finding the primary tree


def primary_checkout(root: Path = REPO_ROOT) -> Optional[Path]:
    """THE primary working tree of this clone, whichever tree asks.

    `git worktree list --porcelain` lists the main working tree FIRST — git's own documented
    order — and every linked one after it. That is the reading, because it is the one this
    file's callers can all make: `make merge` runs in whatever tree invoked it, and the tree
    that needs syncing is usually not that one.

    THE COMMON DIR IS THE CROSS-CHECK AND NOT THE READING. `dirname(git rev-parse
    --git-common-dir)` gets to the same place for an ordinary clone and does NOT in general —
    a `--separate-git-dir` checkout puts the common dir somewhere else entirely, and
    `scripts/worktree-guard.sh` derives it that way only because it has already established it
    is standing in a linked worktree. Disagreement is reported by the caller rather than
    resolved here: two answers to "which directory is the rig" is exactly the class D43 spent
    a decision closing.
    """
    listed = _git(root, "worktree", "list", "--porcelain")
    if not listed.ok:
        return None
    for line in listed.out.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):].strip()
            return Path(path) if path else None
    return None


def _worktree_on(root: Path, branch: str) -> Optional[str]:
    """Which working tree of this clone holds `branch`, if any.

    Asked because part 1 is `git switch main`, and git refuses that outright when another tree
    already has main checked out. A refusal naming that tree is worth a great deal more than
    git's, which arrives at the end of a sync that had already announced itself.
    """
    listed = _git(root, "worktree", "list", "--porcelain")
    if not listed.ok:
        return None
    want = f"branch refs/heads/{branch}"
    where: Optional[str] = None
    for line in listed.out.splitlines():
        if line.startswith("worktree "):
            where = line[len("worktree "):].strip()
        elif line.strip() == want:
            return where
    return None


# ------------------------------------------------------------------------- reading the tree


def _head(root: Path) -> Optional[str]:
    """The branch name, or `None` for a detached HEAD *or* an unreadable one.

    THE TWO `None` CASES ARE SEPARATED DOWNSTREAM RATHER THAN HERE, and deliberately: the
    caller has to ask a second question of a detached HEAD anyway — whether any branch contains
    it — and that question's own failure is the unreadable answer. Distinguishing them here
    would mean a second `rev-parse` every call for a fact that is only wanted on the one path
    that already makes it.
    """
    got = _git(root, "symbolic-ref", "--quiet", "HEAD")
    if got.ok and got.out.startswith("refs/heads/"):
        return got.out[len("refs/heads/"):]
    return None


def mid_operation(root: Path) -> Optional[str]:
    """A sentence naming the half-done git operation, or None.

    THE GIT DIR IS ASKED FOR RATHER THAN ASSUMED TO BE `.git`. For the primary checkout it is
    `<root>/.git` today, and a `--separate-git-dir` clone puts it anywhere; one `rev-parse` is
    cheaper than the class of bug where a guard reads a directory that is not there and reports
    a clean tree.
    """
    got = _git(root, "rev-parse", "--absolute-git-dir")
    if not got.ok or not got.out:
        return "the git directory could not be read"
    git_dir = Path(got.out)
    for name, why in MID_OPERATION:
        try:
            if (git_dir / name).exists():
                return why
        except OSError:
            return "the git directory could not be read"
    return None


def tracked_dirt(root: Path) -> Optional[List[str]]:
    """The porcelain lines for TRACKED changes only. `None` means the status was unreadable.

    UNTRACKED FILES DO NOT BLOCK A SYNC, and that is a measurement rather than a nicety: the
    owner's primary checkout carries an untracked `.preview-check.html` right now, and a guard
    that read it as uncommitted work would refuse every sync forever while being entirely
    right about the bytes. `git switch` and a fast-forward both leave an untracked file exactly
    where it is, so it is not at risk and is not evidence.

    `--porcelain` v1 AND `-uall` OFF, so a directory of exhaust is one `??` line rather than
    four hundred. Nothing here counts them; they are filtered.

    EVERYTHING ELSE BLOCKS, including a staged change that would survive the switch. The rule
    is not "would this be lost" — deciding that correctly for every index state is a
    reimplementation of git — it is "is there work here that is not a commit", and the answer
    is reported rather than judged.
    """
    got = _git(root, "status", "--porcelain")
    if not got.ok:
        return None
    return [line for line in got.out.splitlines() if line and not line.startswith("??")]


def _rev(root: Path, ref: str) -> Optional[str]:
    got = _git(root, "rev-parse", "--verify", "--quiet", ref)
    return got.out or None


def _is_ancestor(root: Path, older: str, newer: str) -> bool:
    return _git(root, "merge-base", "--is-ancestor", older, newer).ok


def _count(root: Path, spec: str) -> int:
    got = _git(root, "rev-list", "--count", spec)
    try:
        return int(got.out)
    except (TypeError, ValueError):
        return 0


# ------------------------------------------------------------------------------- the sync


def _hatch(action: str) -> List[str]:
    if action == REFUSED:
        return [f"  Nothing was moved. Stop being asked:  export {SYNC_ENV}=off"]
    return [f"  Not what you wanted?  {SYNC_ENV}=off turns this off."]


def _refuse(reason: str, headline: str, *detail: str, root: Optional[Path] = None,
            branch: Optional[str] = None) -> Verdict:
    lines = [f"primary-sync: REFUSED — {headline}"]
    lines += [f"  {line}" for line in detail]
    lines += _hatch(REFUSED)
    return Verdict(REFUSED, lines, str(root) if root else None, branch, reason=reason)


def _quiet(reason: str) -> Verdict:
    """NOT SUBJECT. Prints nothing, anywhere, and that is the point of the separate answer."""
    return Verdict(NOT_SUBJECT, [], reason=reason)


def sync(root: Path = REPO_ROOT, confirm: bool = False, fetch: bool = False) -> Verdict:
    """Put the primary checkout of this clone on main, at origin/main. `confirm` performs it.

    `root` IS ANY TREE OF THE CLONE AND THE SUBJECT IS FOUND FROM IT. `make merge` runs in a
    worktree, the SessionStart hook runs in whichever tree the session opened, and the
    supervisor runs in the tree it serves — all three want the same directory acted on, and
    none of them knows its path. Passing the subject in would make three callers responsible
    for a derivation `git worktree list` already owns.

    ONE EXCEPTION, AND IT IS THE SUPERVISOR'S: a caller that IS the primary checkout gets the
    same answer, because `primary_checkout()` resolves to itself.
    """
    try:
        return _sync(root, confirm, fetch)
    except Exception:  # noqa: BLE001 — the fail-open arm; see the module header
        # ITS OWN BUGS ARE SILENT. Three callers run this unasked and none of them is the place
        # to learn that this file has a defect. Nothing was moved, because every write below is
        # the last thing its branch does.
        return _quiet("internal-error")


def _sync(root: Path, confirm: bool, fetch: bool) -> Verdict:
    if os.environ.get(SYNC_ENV) == "off":
        return _quiet("hatch")

    subject = primary_checkout(root)
    if subject is None:
        # The worktree list is a fact it needs and cannot read, so this is the CLOSED
        # direction — loud, and nothing moved.
        return _refuse(
            "unreadable-worktrees",
            "`git worktree list` could not be read, so which directory is the rig is unknown.",
            "This is the one question that decides what may be touched at all, and a guess at",
            "it is a guess at whether a linked worktree is about to be switched under somebody.",
        )

    # A LINKED WORKTREE IS NEVER THE SUBJECT, and the test is `server/ports.py`'s, CALLED
    # rather than respelled — D139's rule, which D158 restates, and for its reason: the
    # primary/linked question has exactly one answer in this repo and a fourth spelling of it
    # is a fourth place for it to be written backwards. ~30 of this machine's worktrees are
    # legitimately on feature branches and have their own stores and ports to be wrong on their
    # own (D43).
    if ports.is_linked_worktree(subject):
        return _quiet("subject-is-linked")

    # GATED ON `main` BEING A REAL LOCAL BRANCH, the same gate `scripts/serve.py:off_main` and
    # `scripts/githooks/post-checkout` use, so a repository whose trunk is called something
    # else is not in violation for it — and so CI, a primary checkout on a detached HEAD with
    # no local `main`, is silent rather than syncing itself mid-run.
    local_main = _rev(subject, MAIN_REF)
    if local_main is None:
        return _quiet("no-local-main")

    if fetch:
        # OPT-IN, AND THE DEFAULT IS OFF FOR A MEASURED REASON. Two of the three callers are on
        # a path where a network call that hangs is the whole cost: a SessionStart hook and a
        # supervisor tick. Neither needs one — every `make merge` fetches before it moves
        # anything, so the `origin/main` this clone holds is current the moment it matters. The
        # deliberate `--fetch` is for a person who wants to ask the network first.
        _git(subject, "fetch", "origin", timeout=120.0)

    origin_main = _rev(subject, ORIGIN_MAIN_REF)
    if origin_main is None:
        # NOT SUBJECT RATHER THAN A REFUSAL, and the difference is which thing is missing. A
        # clone with no `origin/main` has no authority to be synced TO — there is no second
        # part, and announcing that on every session start in a fixture or a `git init` tree
        # would be noise about a state that is not wrong.
        return _quiet("no-origin-main")

    branch = _head(subject)
    # THE BRANCH THE SYNC WOULD LEAVE, which is not the same thing as the branch HEAD is on:
    # on main there is nothing to leave. Computed once and used in every `Verdict` below,
    # because the field means "what this moved the tree off" and a reader — the self-test
    # included — checks it against that meaning.
    left = branch if branch != "main" else None
    holder = _worktree_on(subject, "main")

    # ---- the refusals, all of them before anything is written ----

    half_done = mid_operation(subject)
    if half_done is not None:
        return _refuse(
            "mid-operation",
            f"{subject} is mid-operation — {half_done}.",
            "A branch moved under a half-finished rebase or merge is how one becomes an",
            "afternoon. Finish or abort it there; this will sync on the next look.",
            root=subject, branch=left,
        )

    dirt = tracked_dirt(subject)
    if dirt is None:
        return _refuse(
            "unreadable-status",
            f"`git status` could not be read in {subject}.",
            "Whether there is uncommitted work there is the one fact that decides this, and",
            "not being able to ask is not the same as the answer being no.",
            root=subject, branch=left,
        )
    if dirt:
        shown = dirt[:10]
        more = len(dirt) - len(shown)
        return _refuse(
            "dirty",
            f"{subject} has uncommitted tracked changes, so it is not this file's to move.",
            *shown,
            *([f"… and {more} more"] if more else []),
            "",
            "NAMED RATHER THAN DISCARDED. Untracked files do not block a sync and none is",
            "listed above; these are tracked edits, and committing or reverting them is a",
            "decision somebody has to make.",
            root=subject, branch=left,
        )

    if branch != "main" and holder is not None:
        return _refuse(
            "main-elsewhere",
            f"main is checked out at {holder}, so the primary checkout cannot be put on it.",
            "git permits one working tree per branch and this will not take it from another.",
            f"The rig is {subject}; move main off {holder} and this syncs on the next look.",
            root=subject, branch=left,
        )

    # A DETACHED HEAD CARRYING COMMITS NO BRANCH HOLDS IS THE ONE WAY THIS COULD LOSE WORK.
    # Switching away from a named branch loses nothing — the branch ref survives, and one
    # `git switch` returns. A commit reachable from nothing but HEAD survives only in the
    # reflog, which is not somewhere a person finds work they did not know they had left.
    if branch is None:
        detached = _rev(subject, "HEAD")
        if detached is None:
            return _refuse(
                "unreadable-head",
                f"HEAD could not be read in {subject}.",
                "A detached HEAD may be carrying commits no branch holds; not knowing is not",
                "evidence that it is not.",
                root=subject,
            )
        # `for-each-ref --contains` AND NOT `branch --contains`, AND THAT IS A MEASURED BUG
        # RATHER THAN A PREFERENCE. Measured on git 2.39.3: asked from a detached HEAD,
        # `git branch --all --contains <that commit>` prints `* (HEAD detached from 9e698bd)` —
        # a pseudo-entry for HEAD itself, which is not a branch and is exactly the thing whose
        # absence is being tested. So the orphan arm read "some ref holds it" for every
        # orphaned HEAD there can be, and failed open on the only state here that can lose
        # work. `for-each-ref` lists refs and nothing else, and answers empty.
        contains = _git(subject, "for-each-ref", "--contains", detached,
                        "refs/heads", "refs/remotes", "refs/tags")
        if not contains.ok:
            return _refuse(
                "unreadable-contains",
                f"{subject} is on a detached HEAD and git could not say whether any branch "
                "holds it.",
                "Switching away from a commit nothing points at leaves it in the reflog only.",
                root=subject,
            )
        if not contains.out.strip():
            return _refuse(
                "detached-orphan",
                f"{subject} is on a detached HEAD at {detached[:9]} that NO branch contains.",
                "Switching away would leave those commits reachable from the reflog alone.",
                "  git switch -c <a-name>     then this syncs on the next look",
                root=subject,
            )

    # ---- part 2's own predicate, and it is not the ref hook's ----
    #
    # THE HOOK'S ALLOW RULE 3 ASKS WHETHER THE DESTINATION IS ON `origin/main`. Ours IS
    # `origin/main`, so rule 3 is satisfied by construction and would happily permit a move
    # that discarded local commits. This is the test that does not: `refs/heads/main` must be
    # an ANCESTOR of `refs/remotes/origin/main`, which is true exactly when the move is a
    # fast-forward. Local main ahead, or diverged, fails it and is refused — never rewound,
    # never merged, never forced.
    if local_main == origin_main:
        ff_needed = False
    elif _is_ancestor(subject, MAIN_REF, ORIGIN_MAIN_REF):
        ff_needed = True
    else:
        ahead = _count(subject, f"{ORIGIN_MAIN_REF}..{MAIN_REF}")
        return _refuse(
            "not-a-fast-forward",
            f"{subject}'s main is not behind origin/main, so there is no fast-forward to make.",
            f"main {local_main[:9]} carries {ahead} commit(s) origin/main does not.",
            "",
            "This file only ever fast-forwards. A merge would author a commit nobody reviewed",
            "and a reset would throw those commits away, and D42 is the entry for why neither",
            "is this mechanism's to do: main moves by pull request.",
            root=subject, branch=left,
        )

    switch_needed = branch != "main"
    if not switch_needed and not ff_needed:
        return Verdict(
            ALREADY,
            [f"primary-sync: {subject} is on main at {origin_main[:9]} — already current."],
            str(subject), None, local_main, local_main, 0, "already",
        )

    behind = _count(subject, f"{MAIN_REF}..{ORIGIN_MAIN_REF}") if ff_needed else 0

    if not confirm:
        plan: List[str] = []
        if switch_needed:
            plan.append("git switch main")
        if ff_needed:
            plan.append(f"git merge --ff-only {ORIGIN_MAIN_REF}")
        lines = [
            "primary-sync: PREVIEW — nothing was run.",
            f"  tree:   {subject}",
            f"  would:  {' && '.join(plan)}",
            f"  main:   {local_main[:9]} -> {origin_main[:9]}"
            + (f" ({behind} commits)" if behind else ""),
        ] + _hatch(ALREADY)
        # `PREVIEW` IS ITS OWN ANSWER AND NOT ONE OF THE FOUR. Folding it into `refused` would
        # make `--json` say a tree was refused when it was merely not asked about, and the
        # self-test reads `action` — so the preview and the act cannot be told apart by the one
        # thing that checks they agree.
        return Verdict(
            "preview", lines, str(subject), left, local_main, origin_main, behind, "preview",
        )

    # ---- and now the two commands, in this order ----
    #
    # THE SWITCH COMES FIRST AND THE ORDER IS NOT COSMETIC. With the primary checkout parked on
    # a branch, main is checked out in no tree, so there is nothing for `git merge --ff-only`
    # to run against — part 2 is only available once part 1 has happened. Doing it the other
    # way round means moving `refs/heads/main` with a `git fetch` refspec while the tree still
    # shows the branch's files, which is exactly the half-synced state the ruling is against.
    if switch_needed:
        switched = _git(subject, "switch", "main")
        if not switched.ok:
            return _refuse(
                "switch-failed",
                f"`git switch main` did not complete in {subject}.",
                switched.err or switched.out or "(git said nothing)",
                "",
                "Nothing else was attempted. The tree is on whatever it was on.",
                root=subject, branch=left,
            )

    if ff_needed:
        merged = _git(subject, "merge", "--ff-only", ORIGIN_MAIN_REF)
        if not merged.ok:
            # PART 1 MAY ALREADY HAVE HAPPENED, AND THAT IS SAID RATHER THAN SWALLOWED. This is
            # `scripts/merge-pr.py:local_half`'s bargain in as many words: an incomplete
            # operation reported as one, never a rollback that invents a third state.
            done = "the tree is now on main; " if switch_needed else ""
            return _refuse(
                "ff-failed",
                f"the fast-forward did not complete in {subject}.",
                merged.err or merged.out or "(git said nothing)",
                "",
                f"INCOMPLETE: {done}main is still {local_main[:9]}. Nothing was lost and",
                "nothing was forced. `git -C <tree> pull --ff-only` finishes it by hand.",
                root=subject, branch=left,
            )

    after = _rev(subject, MAIN_REF) or local_main
    parts: List[str] = []
    if switch_needed:
        parts.append(f"{branch or 'a detached HEAD'} -> main")
    if ff_needed:
        parts.append(f"main {local_main[:9]} -> {after[:9]} ({behind} commits)")
    headline = f"primary-sync: {subject}  " + ", ".join(parts) + "."

    lines = [headline]
    if switch_needed and branch is not None:
        # THE WAY BACK, ALWAYS. Nothing was lost — the branch ref is untouched — and the one
        # command that returns is worth more than a paragraph saying so.
        lines.append(f"  Back to it:  git -C {subject} switch {branch}")
    lines += _hatch(SYNCED)
    return Verdict(SYNCED, lines, str(subject), left, local_main, after, behind, "synced")


# --------------------------------------------------------------------------------- the CLI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Put the primary checkout on main, at origin/main. Both parts.",
    )
    parser.add_argument("--confirm", action="store_true",
                        help="perform it. Without this, previews and runs nothing.")
    parser.add_argument("--fetch", action="store_true",
                        help="ask origin first. Off by default: two of the three callers are "
                             "on a path where a hanging network call is the whole cost.")
    parser.add_argument("--quiet", action="store_true",
                        help="print only a sync or a refusal — nothing for a tree already "
                             "current. What the SessionStart hook wants.")
    parser.add_argument("--json", action="store_true", help="the verdict as one object.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    verdict = sync(REPO_ROOT, confirm=args.confirm, fetch=args.fetch)
    if args.json:
        print(verdict.json())
    elif verdict.lines and not (args.quiet and verdict.action == ALREADY):
        for line in verdict.lines:
            print(line)
    # EXIT 0 FOR A REFUSAL, AND THAT IS NOT AN OVERSIGHT. This runs from a SessionStart hook,
    # where a non-zero exit is a session that will not start — the failure mode
    # `scripts/worktree-guard.sh` has a header paragraph about. A refusal is information, and
    # it is on stdout where the reader is.
    return 0


if __name__ == "__main__":
    sys.exit(main())
