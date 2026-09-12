#!/usr/bin/env python3
"""The primary checkout's self-sync, proved by violating it.

A THROWAWAY CLONE WITH ITS OWN WORKTREES, AND NEVER THIS ONE. `scripts/serve-selftest.py` and
`scripts/janitor-selftest.sh` both carry the reason and it is stronger here than in either:
this thing SWITCHES BRANCHES AND MOVES `refs/heads/main`. Run against the real clone it would
switch the owner's live rig — the directory `make launch-agent` keeps a capture server alive
out of, over their real 2,535-card store — which is the exact act that has to be proved safe
rather than performed on the way to proving it.

EVERY ARM IS A REAL REPOSITORY IN A REAL STATE. There is no mock of `git`, no patched
`primary_checkout`, and no fixture that asserts the module was called. The six states the
ruling names are each built with git and then handed to `sync()`, because the whole question
is what git does when this file asks it to, and a mock answers a different question — D158's
own fixture note, one register over.

THE REF HOOK IS ARMED IN ONE ARM AND ONLY ONE. `scripts/githooks/reference-transaction` is what
D42 enforces main with, and the claim this mechanism rests on is that its allow rule 3 already
permits a fast-forward to a commit origin carries. That claim is checkable, so it is checked:
one arm installs the real hook via `core.hooksPath` and proves BOTH directions — the sync's
move is allowed, and a move to a commit origin does not have is still refused. An arm that only
proved the first would pass against a hook that permitted everything.

IN `make check`, NEVER IN THE GIT HOOK. D18: it writes — temp trees, real commits, real ref
moves — and nothing that writes may gate a commit. Same standing and same reason as
`merge-selftest`, `revert-selftest`, `janitor-selftest`, `reap-selftest` and `serve-selftest`.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent

PASS = "\033[32mok\033[0m" if sys.stdout.isatty() else "ok"
FAIL = "\033[31mFAIL\033[0m" if sys.stdout.isatty() else "FAIL"

failures: List[str] = []

# `PKMNSCAN_MAIN=off` FOR THE FIXTURE'S OWN SEED COMMITS AND NOWHERE ELSE. This repo's ref hook
# may be armed through the ambient config and would refuse the fixture's `git init` history for
# reasons that have nothing to do with what is under test. It is deliberately NOT passed to the
# module under test — see `sync_in()` — because whether the hook permits this file's move is one
# of the things being measured.
FIXTURE_ENV = dict(os.environ, PKMNSCAN_MAIN="off", GIT_CONFIG_NOSYSTEM="1")


def check(condition: bool, message: str) -> None:
    print(f"  {PASS if condition else FAIL}  {message}")
    if not condition:
        failures.append(message)


def git(where: Path, *argv: str, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603, S607
        ["git", *argv], cwd=str(where), env=env or FIXTURE_ENV,
        capture_output=True, text=True, check=False,
    )


def seed(where: Path, name: str = "one") -> None:
    for argv in (("config", "user.email", "selftest@example.com"),
                 ("config", "user.name", "selftest"),
                 ("config", "commit.gpgsign", "false")):
        git(where, *argv)
    (where / f"{name}.txt").write_text(name, "utf-8")
    git(where, "add", "-A")
    git(where, "commit", "-qm", name)


def commit(where: Path, name: str) -> str:
    (where / f"{name}.txt").write_text(name, "utf-8")
    git(where, "add", "-A")
    git(where, "commit", "-qm", name)
    return git(where, "rev-parse", "HEAD").stdout.strip()


def build_clone(where: Path, ahead: int = 0) -> Path:
    """A bare origin with `main`, plus a clone of it. `ahead` extra commits ON origin.

    THE ORIGIN IS BARE AND REAL. The module reads `refs/remotes/origin/main`, and the only
    honest way to have one is to have cloned something — a hand-written remote ref would let a
    mutation that stopped reading the remote at all pass.
    """
    origin = where / "origin.git"
    work = where / "seedwork"
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    seed(work)
    git(where, "clone", "-q", "--bare", str(work), str(origin))

    clone = where / "clone"
    git(where, "clone", "-q", str(origin), str(clone))
    for argv in (("config", "user.email", "selftest@example.com"),
                 ("config", "user.name", "selftest"),
                 ("config", "commit.gpgsign", "false")):
        git(clone, *argv)

    if ahead:
        # Commits that exist on origin and not yet in the clone. Pushed from the seed work tree
        # and then FETCHED, so `refs/remotes/origin/main` in the clone is genuinely ahead of
        # `refs/heads/main` — which is the state part 2 exists for.
        for n in range(ahead):
            commit(work, f"origin-{n}")
        push_to_origin(work, origin)
        git(clone, "fetch", "-q", "origin")
        # ASSERTED, BECAUSE THE FIRST DRAFT OF THIS FUNCTION DID NOT PRODUCE THE GAP AT ALL and
        # four arms passed vacuously on the strength of it. `seedwork` is what `origin.git` was
        # cloned FROM, so it has no `origin` remote — `git push -q origin main` there failed
        # silently, every fetch brought back nothing, and `refs/heads/main` was already at
        # `refs/remotes/origin/main` in every fixture. "main is fast-forwarded to origin/main"
        # was green because the two were equal before the call. A fixture that quietly fails to
        # build the state under test is the one failure mode a self-test cannot report.
        gap = git(clone, "rev-list", "--count",
                  "refs/heads/main..refs/remotes/origin/main").stdout.strip()
        assert gap == str(ahead), (
            f"the fixture did not build the gap it was asked for: {gap!r} != {ahead}")
    return clone


def push_to_origin(work: Path, origin: Path) -> None:
    """Push `main` from the seed tree to the bare origin, BY PATH.

    By path because `seedwork` is the repository `origin.git` was cloned from and so has no
    remote of its own — see the assertion in `build_clone` for the four arms that cost.
    """
    pushed = git(work, "push", "-q", str(origin), "main")
    assert pushed.returncode == 0, f"the fixture could not push to its own origin: {pushed.stderr}"


def load_module(tree: Path):
    """The module under test, imported from a COPY inside the fixture.

    Copied rather than imported from `ROOT` for the reason `serve-selftest` copies `serve.py`:
    the mutation sweep edits the copy the test loads, and a sweep that had to edit this
    checkout's own file would be editing a file another session may be reading.
    """
    # THE REAL LAYOUT, MIRRORED, because the module derives `REPO_ROOT` from its own path and
    # then imports `server.ports` off it. A flat copy would import the REAL `server/ports.py`
    # through whatever happened to be on `sys.path`, and a mutation sweep over this file would
    # then be measuring a module wired to a tree it is not in.
    fake_root = tree.parent / "under-test"
    (fake_root / "scripts").mkdir(parents=True, exist_ok=True)
    (fake_root / "server").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts" / "primary_sync.py", fake_root / "scripts" / "primary_sync.py")
    # `server/ports.py` is imported by the module, and `is_linked_worktree` is the one call it
    # makes — CALLED rather than respelled, which is the property this fixture has to preserve
    # for the linked-worktree arm to mean anything.
    shutil.copy2(ROOT / "server" / "ports.py", fake_root / "server" / "ports.py")
    spec = importlib.util.spec_from_file_location(
        "_primary_sync_under_test", fake_root / "scripts" / "primary_sync.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sync_in(module, tree: Path, confirm: bool = True, **kwargs):
    """Run the module against `tree`, with the ambient hatch and `PKMNSCAN_MAIN` LEFT ALONE.

    The fixture sets `PKMNSCAN_MAIN=off` for its own seed commits; passing it here would make
    every arm silently exempt from the ref hook, and one arm's whole subject is that the hook
    permits this move on its own terms.
    """
    return module.sync(tree, confirm=confirm, **kwargs)


def head_branch(tree: Path) -> str:
    return git(tree, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def rev(tree: Path, ref: str) -> str:
    return git(tree, "rev-parse", "--verify", "--quiet", ref).stdout.strip()


def main() -> int:  # noqa: C901 — one arm per state, flat on purpose
    print("primary-sync self-test — the two parts, proved by violating them")

    # ------------------------------------------------- 1. primary on a feature branch
    #
    # THE FIRST OF THE TWO OBSERVED INCIDENTS. D158's account: that one directory on
    # `claude/env-key-rotation` with three live sessions in it, and on
    # `claude/debts-citation-repair` — merged as #282 — with four.
    print("\n  the primary checkout on a feature branch, behind origin")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=3)
        module = load_module(clone)
        git(clone, "switch", "-q", "-c", "claude/a-branch")
        before = rev(clone, "refs/heads/main")

        verdict = sync_in(module, clone)
        check(verdict.action == "synced", "it syncs")
        check(head_branch(clone) == "main", "PART 1: the tree is back on main")
        check(
            rev(clone, "refs/heads/main") == rev(clone, "refs/remotes/origin/main"),
            "PART 2: and main is at origin/main — both parts, one call",
        )
        check(verdict.behind == 3, "the announcement counts the commits main gained (3)")
        check(
            len(verdict.lines) >= 1 and verdict.lines[0].startswith("primary-sync: ")
            and "claude/a-branch -> main" in verdict.lines[0]
            and f"{before[:9]} ->" in verdict.lines[0],
            "and it says what it did IN ONE LINE, naming both parts",
        )
        check(
            any("git -C" in line and "switch claude/a-branch" in line
                for line in verdict.lines),
            "with the way back on it — nothing was lost and one command returns",
        )
        check(
            rev(clone, "refs/heads/claude/a-branch") != "",
            "the branch it left still exists, which is why the switch loses nothing",
        )
        check(
            any(module.SYNC_ENV in line for line in verdict.lines),
            "and the escape hatch is printed, as every refusal and every sync must",
        )

        # IDEMPOTENT, AND THE SECOND CALL IS SILENT-ISH RATHER THAN A SECOND SYNC. Three
        # callers run this unasked; one that announced itself on every tick would be noise
        # nobody reads, which is how the warning it replaces got missed twice.
        again = sync_in(module, clone)
        check(again.action == "already", "a second call answers `already` and moves nothing")

    # ------------------------------------------------- 2. primary ON main but behind
    print("\n  the primary checkout on main, behind origin — part 2 alone")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=2)
        module = load_module(clone)
        check(head_branch(clone) == "main", "the fixture really is on main")
        verdict = sync_in(module, clone)
        check(verdict.action == "synced", "it syncs")
        check(verdict.branch is None, "and reports no branch change, because there was none")
        check(
            rev(clone, "refs/heads/main") == rev(clone, "refs/remotes/origin/main"),
            "main is fast-forwarded to origin/main",
        )
        check(
            "-> main" not in verdict.lines[0],
            "the one line names only the part it did — `70 behind` on main is its own defect",
        )

    # ------------------------------------------------- 3. uncommitted TRACKED work refuses
    print("\n  uncommitted tracked changes — refused, and NAMED")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=1)
        module = load_module(clone)
        git(clone, "switch", "-q", "-c", "claude/dirty")
        (clone / "one.txt").write_text("edited, not committed", "utf-8")
        before_branch = head_branch(clone)
        before_main = rev(clone, "refs/heads/main")

        verdict = sync_in(module, clone)
        check(verdict.action == "refused", "it refuses")
        check(verdict.reason == "dirty", "for being dirty, by name")
        check(
            any("one.txt" in line for line in verdict.lines),
            "and NAMES THE FILE rather than counting it — the refusal is the useful half",
        )
        check(head_branch(clone) == before_branch, "the tree was not switched")
        check(rev(clone, "refs/heads/main") == before_main, "and main was not moved")
        check(
            any(f"{module.SYNC_ENV}=off" in line for line in verdict.lines),
            "the escape hatch is on the refusal",
        )

        # A STAGED change is uncommitted work too, and a guard that read only the worktree
        # would call this clean.
        (clone / "one.txt").write_text("one", "utf-8")
        (clone / "staged.txt").write_text("new", "utf-8")
        git(clone, "add", "staged.txt")
        staged = sync_in(module, clone)
        check(
            staged.action == "refused" and staged.reason == "dirty"
            and any("staged.txt" in line for line in staged.lines),
            "a STAGED addition refuses too — `git status` is asked, not the worktree alone",
        )

    # ------------------------------------------------- 4. untracked exhaust does NOT block
    #
    # THE MEASURED CASE. The owner's primary checkout carries an untracked
    # `.preview-check.html` right now; a guard that read it as uncommitted work would refuse
    # every sync forever while being entirely right about the bytes.
    print("\n  untracked exhaust only — it must still sync")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=2)
        module = load_module(clone)
        git(clone, "switch", "-q", "-c", "claude/exhaust")
        (clone / ".preview-check.html").write_text("<!doctype html>", "utf-8")
        (clone / "scratch").mkdir()
        (clone / "scratch" / "notes.txt").write_text("exhaust", "utf-8")

        verdict = sync_in(module, clone)
        check(verdict.action == "synced", "it syncs past untracked files")
        check(head_branch(clone) == "main", "part 1 happened")
        check(
            rev(clone, "refs/heads/main") == rev(clone, "refs/remotes/origin/main"),
            "part 2 happened",
        )
        check(
            (clone / ".preview-check.html").exists(),
            "and the untracked file is still there — a switch never touches one",
        )
        check(
            not any(".preview-check.html" in line for line in verdict.lines),
            "nor is it named, because it is not evidence of anything",
        )

    # ------------------------------------------------- 5. a LINKED worktree is untouched
    #
    # D43's whole purchase, and the one thing the ruling forbids absolutely. The test is
    # `server/ports.py:is_linked_worktree` — a linked worktree's `.git` is a FILE — and it is
    # the fact most likely to be written backwards, which is why both directions are asserted
    # from the same fixture.
    print("\n  a linked worktree off main — left completely alone")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=2)
        module = load_module(clone)
        linked = where / "linked"
        git(clone, "worktree", "add", "-q", "-b", "claude/in-a-worktree", str(linked))
        check(
            head_branch(linked) == "claude/in-a-worktree",
            "the fixture's linked worktree really is off main",
        )
        check((linked / ".git").is_file(), "and its `.git` really is a FILE, which is the test")

        # Asked FROM the linked worktree, which is how `make merge` and a SessionStart hook in
        # a worktree both reach this. The subject must resolve to the PRIMARY tree, and the
        # worktree must not be the thing that moves.
        # `resolve()` ON BOTH SIDES. `git worktree list` reports real paths, and on macOS
        # `tempfile` hands out `/var/folders/...`, which is a symlink to `/private/var/...`.
        # Comparing the unresolved fixture path against git's answer fails on a machine
        # difference and says nothing about the module.
        verdict = module.sync(linked, confirm=True)
        check(
            verdict.action == "synced"
            and Path(verdict.root or "").resolve() == clone.resolve(),
            "asked from inside the worktree, it syncs the PRIMARY checkout and says which",
        )
        check(
            head_branch(linked) == "claude/in-a-worktree",
            "and the LINKED worktree is still on its own branch — never the subject",
        )
        check(
            not (linked / "origin-0.txt").exists(),
            "its working files were not changed either",
        )

        # THE SECOND LOCK ON THE ONE DOOR THE RULING FORBIDS OPENING, AND IT NEEDED ITS OWN
        # SUBJECT. `subject` comes from `primary_checkout`, which returns the PRIMARY tree — so
        # `is_linked_worktree(subject)` is False in every state this fixture can build, and a
        # mutation deleting that test SURVIVED the whole sweep. It cannot decide anything while
        # `primary_checkout` is right.
        #
        # D158's own sweep DELETED a line in exactly that position, on the ground that a line
        # which cannot change a verdict is a sentence about a guard rather than one. THIS ONE IS
        # KEPT INSTEAD, and the difference is what it guards: "never a linked worktree" is the
        # prohibition the owner's ruling is most absolute about, and `primary_checkout`'s own
        # docstring records that the obvious refactor of it — deriving the path from
        # `--git-common-dir` — does NOT generalise to a `--separate-git-dir` checkout. So this
        # test is what still holds if that derivation is ever changed, and the way to prove a
        # backstop is to take away what stands in front of it.
        original = module.primary_checkout
        module.primary_checkout = lambda *a, **k: linked
        try:
            handed = module.sync(clone, confirm=True)
        finally:
            module.primary_checkout = original
        check(
            handed.action == "not-subject" and handed.reason == "subject-is-linked"
            and handed.lines == [],
            "handed a LINKED worktree as the subject, it refuses to act and says nothing — the "
            "backstop if `primary_checkout` is ever changed",
        )
        check(
            head_branch(linked) == "claude/in-a-worktree",
            "and that worktree is still on its own branch, untouched by the attempt",
        )

        check(
            (module.primary_checkout(linked) or Path("/nowhere")).resolve() == clone.resolve(),
            "`primary_checkout` from a worktree resolves to the primary tree, first-listed",
        )
        check(
            module.ports.is_linked_worktree(linked)
            and not module.ports.is_linked_worktree(clone),
            "and the primary/linked test is the one in server/ports.py, both directions",
        )

    # ------------------------------------------------- 6. not a fast-forward refuses
    print("\n  local main carries commits origin does not — refused, not rewound")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=2)
        module = load_module(clone)
        # A local commit on main. `PKMNSCAN_MAIN=off` because committing ON main is exactly
        # what D42's hook refuses, and the state is the fixture rather than the subject.
        local_tip = commit(clone, "local-only")
        git(clone, "switch", "-q", "-c", "claude/elsewhere")
        verdict = sync_in(module, clone)
        check(verdict.action == "refused", "it refuses")
        check(verdict.reason == "not-a-fast-forward", "for not being a fast-forward, by name")
        check(
            rev(clone, "refs/heads/main") == local_tip,
            "and main STILL CARRIES the local commit — never reset, never merged, never forced",
        )
        check(
            head_branch(clone) == "claude/elsewhere",
            "part 1 did not run either: the refusals are all decided before anything is written",
        )
        check(
            any("fast-forward" in line for line in verdict.lines),
            "and the refusal says which of the two parts it could not do",
        )

        # DIVERGED, which is the other half of the same predicate and a different repository
        # state: origin has commits the clone does not AND the clone has one origin does not.
        git(clone, "switch", "-q", "main")
        git(clone, "reset", "-q", "--hard", "refs/remotes/origin/main",
            env=dict(FIXTURE_ENV, PKMNSCAN_MAIN="off"))
        commit(clone, "diverging")
        origin_work = where / "seedwork"
        commit(origin_work, "origin-later")
        push_to_origin(origin_work, where / "origin.git")
        git(clone, "fetch", "-q", "origin")
        diverged = sync_in(module, clone)
        check(
            diverged.action == "refused" and diverged.reason == "not-a-fast-forward",
            "a DIVERGED main refuses on the same predicate, which covers both shapes",
        )

    # ------------------------------------------------- 7. mid-operation refuses
    print("\n  a half-finished git operation — refused")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=1)
        module = load_module(clone)
        git(clone, "switch", "-q", "-c", "claude/conflicted")
        # A REAL CONFLICTED MERGE, not a touched `MERGE_HEAD`. The file has to exist for the
        # reason git puts it there, or the arm proves a `Path.exists` call and not a guard.
        (clone / "one.txt").write_text("branch side", "utf-8")
        git(clone, "commit", "-qam", "branch edits one.txt")
        git(clone, "switch", "-q", "-c", "claude/other", "main")
        (clone / "one.txt").write_text("other side", "utf-8")
        git(clone, "commit", "-qam", "other edits one.txt")
        merging = git(clone, "merge", "claude/conflicted")
        check(
            merging.returncode != 0
            and (Path(clone / ".git" / "MERGE_HEAD")).exists(),
            "the fixture really is mid-merge, with MERGE_HEAD on disk",
        )
        verdict = sync_in(module, clone)
        check(verdict.action == "refused", "it refuses")
        check(verdict.reason == "mid-operation", "for being mid-operation, by name")
        check(head_branch(clone) == "claude/other", "and nothing was switched under it")
        git(clone, "merge", "--abort")

        # A REBASE is the other shape, and it leaves a DIRECTORY rather than a file — which is
        # the half a guard checking only for `MERGE_HEAD` misses.
        git(clone, "switch", "-q", "claude/other")
        rebasing = git(clone, "rebase", "claude/conflicted")
        in_rebase = ((clone / ".git" / "rebase-merge").exists()
                     or (clone / ".git" / "rebase-apply").exists())
        check(
            rebasing.returncode != 0 and in_rebase,
            "and the fixture can produce a stopped REBASE, whose marker is a directory",
        )
        mid_rebase = sync_in(module, clone)
        check(
            mid_rebase.action == "refused" and mid_rebase.reason == "mid-operation",
            "a stopped rebase refuses too — the marker is a directory, not a file",
        )
        git(clone, "rebase", "--abort")

    # ------------------------------------------------- 8. main held by another worktree
    print("\n  main checked out in another worktree — refused, and it says where")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=1)
        module = load_module(clone)
        git(clone, "switch", "-q", "-c", "claude/parked")
        elsewhere = where / "holds-main"
        git(clone, "worktree", "add", "-q", str(elsewhere), "main")
        verdict = sync_in(module, clone)
        check(verdict.action == "refused", "it refuses")
        check(verdict.reason == "main-elsewhere", "for main being held elsewhere, by name")
        check(
            any(str(elsewhere) in line for line in verdict.lines),
            "and names the tree holding it, which git's own refusal does only at the end",
        )
        check(head_branch(clone) == "claude/parked", "nothing moved")

    # ------------------------------------------------- 9. a detached HEAD, both shapes
    print("\n  a detached HEAD — synced when a branch holds it, refused when none does")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=2)
        module = load_module(clone)
        git(clone, "switch", "-q", "--detach", "refs/heads/main")
        held = sync_in(module, clone)
        check(
            held.action == "synced" and head_branch(clone) == "main",
            "a detached HEAD at a commit main holds syncs — nothing is at risk",
        )

        # AND THE ONE WAY THIS COULD LOSE WORK. A commit reachable from nothing but HEAD
        # survives a switch only in the reflog, which is not somewhere a person finds work they
        # did not know they had left.
        git(clone, "switch", "-q", "--detach", "HEAD")
        orphan = commit(clone, "orphan")
        verdict = sync_in(module, clone)
        check(verdict.action == "refused", "it refuses")
        check(verdict.reason == "detached-orphan", "for an orphaned HEAD, by name")
        check(
            rev(clone, "HEAD") == orphan,
            "and the tree is still standing on that commit, so it is still findable",
        )
        check(
            any(orphan[:9] in line for line in verdict.lines),
            "with the commit named, because nothing else points at it",
        )

    # ------------------------------------------------- 10. the ref hook's allow rule 3
    #
    # THE CLAIM THIS WHOLE MECHANISM RESTS ON, CHECKED RATHER THAN CITED. Both directions from
    # one armed hook, because an arm proving only that the sync is permitted would pass against
    # a hook that permitted everything.
    print("\n  D42's ref hook, armed: it permits this move and still refuses a local one")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=2)
        module = load_module(clone)
        hooks = where / "hooks"
        hooks.mkdir()
        shutil.copy2(ROOT / "scripts" / "githooks" / "reference-transaction",
                     hooks / "reference-transaction")
        (hooks / "reference-transaction").chmod(0o755)
        git(clone, "config", "core.hooksPath", str(hooks))

        # The hatch is NOT set for these two — the hook's own judgement is the measurement.
        armed = dict(os.environ)
        armed.pop("PKMNSCAN_MAIN", None)
        armed["GIT_CONFIG_NOSYSTEM"] = "1"

        refused = git(clone, "branch", "-f", "main", "refs/remotes/origin/main~1", env=armed)
        # `origin/main~1` IS on origin/main's history, so that one is allowed by rule 3 too;
        # the refusal has to be a commit origin does NOT carry.
        git(clone, "switch", "-q", "-c", "claude/local")
        local_tip = commit(clone, "never-pushed")
        refused = git(clone, "branch", "-f", "main", local_tip, env=armed)
        check(
            refused.returncode != 0 and "REFUSED" in (refused.stderr or ""),
            "the armed hook still refuses a move to a commit origin does not carry",
        )

        git(clone, "switch", "-q", "claude/local")
        os.environ.pop("PKMNSCAN_MAIN", None)
        verdict = module.sync(clone, confirm=True)
        check(
            verdict.action == "synced",
            "and the sync's fast-forward goes through WITH THAT HOOK ARMED — allow rule 3",
        )
        check(
            rev(clone, "refs/heads/main") == rev(clone, "refs/remotes/origin/main"),
            "main really did land on origin/main under the hook's own judgement",
        )

    # ------------------------------------------------- 11. the hatch, and the quiet states
    print("\n  the hatch, and the three states that must print nothing at all")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=2)
        module = load_module(clone)
        git(clone, "switch", "-q", "-c", "claude/hatched")

        os.environ[module.SYNC_ENV] = "off"
        try:
            hatched = module.sync(clone, confirm=True)
        finally:
            os.environ.pop(module.SYNC_ENV, None)
        check(
            hatched.action == "not-subject" and hatched.lines == []
            and head_branch(clone) == "claude/hatched",
            f"{module.SYNC_ENV}=off does nothing and says nothing",
        )

        # PREVIEW PRESSES NOTHING, which is what `make merge ARGS=<n>` inherits.
        preview = module.sync(clone, confirm=False)
        check(
            preview.action == "preview" and head_branch(clone) == "claude/hatched"
            and rev(clone, "refs/heads/main") != rev(clone, "refs/remotes/origin/main"),
            "without --confirm it previews and presses neither part",
        )
        check(
            any("git switch main" in line and "--ff-only" in line for line in preview.lines),
            "and prints both commands it would run",
        )

    # A repository with no `origin/main`, and one whose trunk is called something else. Both
    # are SILENT, and both are states the fixtures above cannot also be in — which is exactly
    # how a gate goes unnoticed by every other arm (D158's own finding).
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        lonely = where / "lonely"
        lonely.mkdir()
        git(lonely, "init", "-q", "-b", "main")
        seed(lonely)
        git(lonely, "switch", "-q", "-c", "topic")
        module = load_module(lonely)
        check(
            module.sync(lonely, confirm=True).action == "not-subject"
            and head_branch(lonely) == "topic",
            "a clone with no origin/main has no authority to sync to, and is silent",
        )

        foreign = where / "foreign"
        foreign.mkdir()
        git(foreign, "init", "-q", "-b", "master")
        seed(foreign, "f")
        git(foreign, "switch", "-q", "-c", "topic")
        check(
            module.sync(foreign, confirm=True).action == "not-subject",
            "and a repository whose trunk is called something else is not in violation for it",
        )

    # ------------------------------------------------- 11b. CI's shape: no LOCAL main
    #
    # THE ARM THAT KILLS A MUTATION SURVIVOR, and the state is a real one: on CI the checkout is
    # a PRIMARY tree standing on a detached HEAD with `origin/main` present and no local `main`
    # at all. The `main`-is-a-real-local-branch gate is what keeps this silent, and with that
    # gate deleted the ancestry test asks about a ref that does not exist, fails, and prints a
    # `not-a-fast-forward` REFUSAL on every session start of every pull request.
    #
    # The fixtures above cannot reach it: the lonely and foreign repos have no `origin/main`
    # either, so they return one gate earlier and mask this one — which is exactly how a gate
    # goes unnoticed by every other arm (D158's own finding, and it happened again here).
    print("\n  CI's shape — origin/main present, no local main — must be silent")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=2)
        module = load_module(clone)
        git(clone, "switch", "-q", "--detach", "refs/remotes/origin/main")
        git(clone, "branch", "-q", "-D", "main")
        check(
            rev(clone, "refs/heads/main") == "" and rev(clone, "refs/remotes/origin/main") != "",
            "the fixture really has origin/main and no local main",
        )
        verdict = module.sync(clone, confirm=True)
        check(
            verdict.action == "not-subject" and verdict.reason == "no-local-main"
            and verdict.lines == [],
            "a primary checkout with no local `main` is not in violation, and says nothing",
        )

    # ------------------------------------------------- 11c. `--ff-only` is load-bearing
    #
    # A SECOND ARM FOR THE SAME RULE, BECAUSE THE TWO GUARDS OVERLAP AND ONLY ONE WAS PROVED.
    # The ancestry predicate refuses a diverged main before the merge is reached, so in every
    # state this fixture can build, `git merge --ff-only` and a plain `git merge` behave
    # identically — measured: a mutation dropping `--ff-only` SURVIVED the whole sweep.
    #
    # A survivor is information rather than something to argue away. What it says is that the
    # flag is a backstop with nothing standing on it, and the way to give it a subject is to
    # take the other guard away: `_is_ancestor` is neutered here, the diverged main reaches the
    # merge, and `--ff-only` is the only thing left that can stop a merge commit being authored
    # in the owner's rig by a background process. It is defence in depth, and now it is proved.
    print("\n  `--ff-only` alone stops a diverged main, with the ancestry test neutered")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=1)
        module = load_module(clone)
        # A genuinely diverged main: a local commit on it, and a later commit on origin.
        local_tip = commit(clone, "local-only")
        origin_work = where / "seedwork"
        commit(origin_work, "origin-later")
        push_to_origin(origin_work, where / "origin.git")
        git(clone, "fetch", "-q", "origin")
        check(
            not module._is_ancestor(clone, module.MAIN_REF, module.ORIGIN_MAIN_REF),
            "the fixture's main really has diverged from origin/main",
        )

        original = module._is_ancestor
        module._is_ancestor = lambda *a, **k: True   # the predicate, removed
        try:
            verdict = module.sync(clone, confirm=True)
        finally:
            module._is_ancestor = original
        check(
            verdict.action == "refused" and verdict.reason == "ff-failed",
            "the merge itself refuses — `--ff-only` is what makes that a refusal and not a "
            "merge commit authored in the rig by a background process",
        )
        check(
            rev(clone, "refs/heads/main") == local_tip,
            "and main is exactly where it was: no merge commit, nothing rewound",
        )
        check(
            any("INCOMPLETE" in line for line in verdict.lines),
            "reported as an INCOMPLETE operation, because part 1 had already run",
        )

    # ------------------------------------------------- 12. fail OPEN on its own bugs
    #
    # `scripts/reap.py:hook`'s rule, and the one arm that cannot be built from a repository
    # state: the module's own defect. Three callers run this unasked and none of them is the
    # place to learn it has one.
    print("\n  its own bugs fail OPEN and silently; an unreadable target fails CLOSED and loud")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        clone = build_clone(where, ahead=1)
        module = load_module(clone)
        git(clone, "switch", "-q", "-c", "claude/boom")

        original = module.primary_checkout
        module.primary_checkout = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            blew_up = module.sync(clone, confirm=True)
        finally:
            module.primary_checkout = original
        check(
            blew_up.action == "not-subject" and blew_up.lines == []
            and blew_up.reason == "internal-error",
            "an exception anywhere in it answers `not-subject`, silently, and moves nothing",
        )
        check(head_branch(clone) == "claude/boom", "and the tree is exactly as it was")

        # CLOSED, AND LOUD, on a fact it needs and cannot read. Not knowing whether a tree is
        # safe to move is not evidence that it is.
        module.primary_checkout = lambda *a, **k: None
        try:
            blind = module.sync(clone, confirm=True)
        finally:
            module.primary_checkout = original
        check(
            blind.action == "refused" and blind.reason == "unreadable-worktrees"
            and blind.lines,
            "an unreadable worktree list REFUSES and prints, rather than guessing",
        )

        original_dirt = module.tracked_dirt
        module.tracked_dirt = lambda *a, **k: None
        try:
            unreadable = module.sync(clone, confirm=True)
        finally:
            module.tracked_dirt = original_dirt
        check(
            unreadable.action == "refused" and unreadable.reason == "unreadable-status",
            "and an unreadable `git status` refuses too — the same direction, the same reason",
        )

    print()
    if failures:
        print(f"{FAIL}  {len(failures)} of the sync's behaviours are wrong")
        for line in failures:
            print(f"       {line}")
        return 1
    print(f"{PASS}  the primary checkout syncs both parts, and refuses the six ways it must")
    return 0


if __name__ == "__main__":
    sys.exit(main())
