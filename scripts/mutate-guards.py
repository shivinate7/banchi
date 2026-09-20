#!/usr/bin/env python3
"""Mutation-test this repo's guards, and verify their mutation anchors fast.

WHY THIS EXISTS. This repo mutation-tests its guards by hand and records the arm counts in
PROSE — a sentence in CLAUDE.md or in `scripts/checks.py`. Nothing re-runs those sweeps and
nothing checks the counts. `scripts/checks.py`'s own `claim-selftest` entry is the proof this
drifts: it says "FORTY-TWO arms — the count in this sentence said sixteen over a file that held
eighteen, which is what a prose count does." A person caught that by hand. Nothing else would
have.

THE MODEL THIS COPIES is `~/.claude/hooks/mutate_guard.py` (read it before changing this file):
copy the guard to a temp file, apply ONE literal string replacement per mutation, run the
guard's OWN suite against the copy, and require the suite to go red. A mutation the suite does
not catch SURVIVES, and any survivor fails the run. A mutation whose anchor text is no longer
found in the CURRENT guard source is STALE — the source moved on and the mutation proves
nothing — and that fails LOUDLY, with an ERROR line, rather than being silently skipped or
silently counted either way.

TWO MODES:

  python3 scripts/mutate-guards.py                 the real run: copies each guard, applies
                                                     every mutation, and runs that guard's own
                                                     selftest suite against the mutated copy.
                                                     Slow — it shells out to real selftests,
                                                     several of which build throwaway git
                                                     repositories. Off the commit path (D18):
                                                     nothing that writes may gate a commit.

  python3 scripts/mutate-guards.py --verify-anchors fast: no subprocess, no suite run. For every
                                                     mutation, asserts the anchor text is
                                                     present EXACTLY ONCE in the guard file it
                                                     targets right now. This is the half meant
                                                     to sit in `make check` — a stale anchor is
                                                     exactly how a hand-maintained mutation list
                                                     rots, silently, the way the arm count in
                                                     `scripts/checks.py` did.

  python3 scripts/mutate-guards.py --counts         print the mutation count per guard and
                                                     the total, and exit 0. Read-only, no
                                                     subprocess. This is the reconciliation
                                                     input: a later session (or a docs-audit
                                                     row) compares these numbers against the
                                                     prose arm counts in CLAUDE.md and
                                                     `scripts/checks.py` and corrects whichever
                                                     one is wrong.

SCOPE. This does not attempt every mutation-tested guard in `make check` — the brief that built
this file named five in priority order and this covers those five plus one: `guard-shell.py` (9
clauses), `silent-write-guard.py`, `reap.py`, `primary_sync.py`, `revert-audit.py`, and since
2026-09-20 `merge-pr.py`, whose suite is `claim-selftest.py` rather than a `.sh` beside it. Each guard's
mutation list writes at least one arm per RULE that guard enforces, following the parent
model's own comment ("Each one breaks exactly one rule. One mutation per rule at least"). A
guard this file does NOT cover is not listed here at all — reporting a guard as "0 arms, not
really tested" would read as coverage, which is worse than naming nothing (the brief's own
words). See the wrap-up report for which guards were left out and why.

HOW A MUTATED GUARD'S OWN SUITE IS RUN. Three of these guards ship a `.sh` selftest that
resolves its subject (`GUARD="$HERE/guard-shell.py"`) relative to ITS OWN location — so the
sweep copies the WHOLE `scripts/` directory into a throwaway tree, writes the mutated guard
into the copy, and runs the copied `.sh` selftest from there. `primary_sync.py`'s selftest
(`sync-selftest.py`) does the same thing itself, one register up — `load_module()` derives
`ROOT` from its own file location and copies `ROOT/scripts/primary_sync.py` (plus
`server/ports.py`) into a nested fixture — so mirroring the real layout (`<tmp>/scripts/`,
`<tmp>/server/`) and mutating the copy IN PLACE is what makes that copy step pick up the
mutation. `revert-audit.py` needs none of this: it is a single, dependency-free file with its
own `selftest` subcommand, so the runner copies just that file and calls
`python3 <copy> selftest`. `merge-pr.py` takes the whole-directory copy the `.sh` guards take,
with one addition: it imports `scripts/primary_sync.py`, which imports `server.ports` off its
OWN `parents[1]`, so the fixture mirrors that package too. Without it every mutant dies of a
`ModuleNotFoundError` and reads as caught, which is a survivor this file could not see.

Stdlib only.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, List, NamedTuple, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


class Mutation(NamedTuple):
    label: str          # names the rule this arm breaks
    anchor: str          # literal text, must appear exactly once in the CURRENT guard source
    replacement: str     # the mutated text


class SuiteResult(NamedTuple):
    returncode: int
    output: str


class GuardSpec(NamedTuple):
    name: str                                   # the `make X-selftest` target this covers
    guard_path: Path                            # the real file this file mutates a COPY of
    mutations: Sequence[Mutation]
    # Builds a throwaway tree with the mutated guard already in place at the right relative
    # path, and returns a callable that runs that guard's own suite and reports (code, output).
    prepare_and_run: Callable[[Path, str], SuiteResult]


# --------------------------------------------------------------------- suite runners, per guard


def _run(argv: Sequence[str], cwd: Optional[Path] = None, timeout: float = 300.0) -> SuiteResult:
    try:
        result = subprocess.run(
            list(argv), cwd=str(cwd) if cwd else None, capture_output=True, text=True,
            timeout=timeout,
        )
        return SuiteResult(result.returncode, result.stdout + result.stderr)
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") + (exc.stderr or "")
        return SuiteResult(124, out + "\nTIMEOUT after %.0fs" % timeout)


def _copy_scripts_dir(work: Path) -> Path:
    """A full copy of `scripts/`, so a `.sh` selftest resolves its guard relative to itself."""
    dest = work / "scripts"
    shutil.copytree(SCRIPTS, dest)
    return dest


def _write_mutated(path: Path, mutated_source: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(mutated_source)


def _sh_suite_runner(guard_filename: str, selftest_filename: str):
    """Build a `prepare_and_run` for a guard whose suite is a `.sh` beside it in `scripts/`."""

    def run(work: Path, mutated_source: str) -> SuiteResult:
        copy_dir = _copy_scripts_dir(work)
        _write_mutated(copy_dir / guard_filename, mutated_source)
        return _run(["bash", str(copy_dir / selftest_filename)], cwd=copy_dir, timeout=600.0)

    return run


def _py_suite_runner(guard_filename: str, selftest_filename: str):
    """The same as `_sh_suite_runner` for a suite that is a `python3` beside it in `scripts/`.

    `claim-selftest.py` derives its subject as `ROOT/scripts/merge-pr.py` with `ROOT` two
    levels up from itself, so the whole-directory copy puts the mutated file exactly where
    that derivation lands — no different from the `.sh` case, one interpreter along.
    """

    def run(work: Path, mutated_source: str) -> SuiteResult:
        copy_dir = _copy_scripts_dir(work)
        _write_mutated(copy_dir / guard_filename, mutated_source)
        # `merge-pr.py` imports `scripts/primary_sync.py`, which imports `server.ports` off
        # ITS OWN `parents[1]` — so the fixture needs that package too, or every mutant dies
        # of a ModuleNotFoundError and reads as caught. A red for the wrong reason is a
        # survivor this file cannot see, and it is also the cry-wolf shape the house rule
        # names: a mutation sweep that goes red whatever you do proves nothing at all.
        server = work / "server"
        server.mkdir(parents=True, exist_ok=True)
        for name in ("__init__.py", "ports.py"):
            source = ROOT / "server" / name
            if source.exists():
                shutil.copy2(source, server / name)
        return _run([sys.executable, str(copy_dir / selftest_filename)], cwd=copy_dir,
                    timeout=900.0)

    return run


def _sync_suite_runner():
    """`sync-selftest.py`'s own `load_module()` copies `ROOT/scripts/primary_sync.py` and
    `ROOT/server/ports.py` into a nested fixture, where `ROOT` is derived from wherever
    `sync-selftest.py` itself sits. So this mirrors the real tree just enough for that
    derivation to land on the mutated copy: `<tmp>/scripts/{sync-selftest.py, primary_sync.py}`
    and `<tmp>/server/ports.py`.
    """

    def run(work: Path, mutated_source: str) -> SuiteResult:
        (work / "scripts").mkdir(parents=True, exist_ok=True)
        (work / "server").mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCRIPTS / "sync-selftest.py", work / "scripts" / "sync-selftest.py")
        _write_mutated(work / "scripts" / "primary_sync.py", mutated_source)
        shutil.copy2(ROOT / "server" / "ports.py", work / "server" / "ports.py")
        return _run([sys.executable, str(work / "scripts" / "sync-selftest.py")],
                    cwd=work, timeout=600.0)

    return run


def _revert_audit_suite_runner():
    """A single dependency-free file with its own `selftest` subcommand — copy it, run it."""

    def run(work: Path, mutated_source: str) -> SuiteResult:
        copy_path = work / "revert-audit.py"
        _write_mutated(copy_path, mutated_source)
        return _run([sys.executable, str(copy_path), "selftest"], cwd=work, timeout=600.0)

    return run


# ----------------------------------------------------------------------------- the mutations
#
# One mutation per RULE at least, per the parent model's own comment. Each label names the
# rule it breaks. Anchors are literal text copied from the guard at the commit this file was
# built against — `--verify-anchors` is what notices when one of them has moved.

GUARD_SHELL = SCRIPTS / "guard-shell.py"

GUARD_SHELL_MUTATIONS: Tuple[Mutation, ...] = (
    Mutation(
        "checkout clause: never recognise a restore verb",
        '        if verb not in _RESTORE_VERBS:\n            continue',
        '        if True:\n            continue',
    ),
    Mutation(
        "tree clause (Bash half): never flag a write outside the checkout",
        '        verdict = _outside(write.target, write.cwd, root)\n        if verdict:',
        '        verdict = _outside(write.target, write.cwd, root)\n        if False:',
    ),
    Mutation(
        "tree clause (Write|Edit half): never flag a write outside the checkout",
        '    verdict = _outside(file_path, cwd, root)\n    if not verdict:\n'
        '        return Verdict([], [])\n    return Verdict([_tree_refusal(verdict[0], root, file_path)], [])',
        '    verdict = _outside(file_path, cwd, root)\n    if not verdict:\n'
        '        return Verdict([], [])\n    return Verdict([], [])',
    ),
    Mutation(
        "gh clause: never refuse a field with no method",
        '        if has_method or not fields:\n            continue',
        '        if True:\n            continue',
    ),
    Mutation(
        "link clause: never refuse ln -s at an existing path",
        '        if not symbolic or safe or not operands:\n            continue',
        '        if True:\n            continue',
    ),
    Mutation(
        "wait clause: never refuse a loop that polls a pattern",
        '        poller = _polls_a_pattern(loop.condition)\n        if poller:',
        '        poller = _polls_a_pattern(loop.condition)\n        if False:',
    ),
    Mutation(
        "push clause: never refuse a push to a differently-named tracked upstream",
        '            tracked = _tracked_branch(branch, remote, where)\n'
        '            if tracked is None or tracked == branch:\n                continue',
        '            tracked = _tracked_branch(branch, remote, where)\n'
        '            if True:\n                continue',
    ),
    Mutation(
        "stash clause: stop treating `git stash pop` as always-refused",
        '_STASH_ALWAYS = {"pop", "clear"}',
        '_STASH_ALWAYS = {"clear"}',
    ),
    Mutation(
        "reset clause: never recognise a discarding mode",
        '_RESET_DISCARDING_MODES = {"--hard", "--merge", "--keep"}',
        '_RESET_DISCARDING_MODES = set()',
    ),
    Mutation(
        "narrate clause: a truncating filter is no longer one",
        '_TRUNCATING = {"tail", "head"}',
        '_TRUNCATING = set()',
    ),
    Mutation(
        "narrate clause: never recognise the command that narrates",
        '        for name, goal, _, _ in NARRATORS:\n            if goal in goals:\n'
        '                return name',
        '        for name, goal, _, _ in NARRATORS:\n            if False:\n'
        '                return name',
    ),
    Mutation(
        "narrate clause: a PREVIEW is refused too — the cry-wolf half",
        '    if not any("--confirm" in word for word in argv):\n        return ""',
        '    if False:\n        return ""',
    ),
)

SILENT_WRITE_GUARD = SCRIPTS / "silent-write-guard.py"

SILENT_WRITE_MUTATIONS: Tuple[Mutation, ...] = (
    Mutation(
        "a redirect to /dev/null is not a discard",
        '        if where.kind in (NULL, CLOSED):\n            return True',
        '        if False:\n            return True',
    ),
    Mutation(
        "a file the command never reads back is exempted anyway (never a discard)",
        '        for other in every:\n            if other is not mine and where.path in other.argv:\n'
        '                return False\n        return True',
        '        for other in every:\n            if other is not mine and where.path in other.argv:\n'
        '                return False\n        return False',
    ),
    Mutation(
        "git commit is never recognised as a write",
        '        if verb == "commit" and "--dry-run" not in flags:\n            return "git commit"',
        '        if False:\n            return "git commit"',
    ),
    Mutation(
        "git push is never recognised as a write",
        '        if verb == "push" and not flags & {"--dry-run", "-n"}:\n            return "git push"',
        '        if False:\n            return "git push"',
    ),
    Mutation(
        "git pull is never recognised as a write",
        '        if verb == "pull":\n            return "git pull"',
        '        if False:\n            return "git pull"',
    ),
    Mutation(
        "`make merge` is never recognised as a write",
        '        if "merge" in goals:\n            return "make merge"',
        '        if False:\n            return "make merge"',
    ),
    Mutation(
        "the advice for a BLOCKING verb becomes the pipe the neighbouring guard refuses",
        '_NARRATED = frozenset({"make merge"})',
        '_NARRATED = frozenset()',
    ),
    Mutation(
        "`gh pr merge` is never recognised as a write",
        '    if (head == "gh" or head.endswith("/gh")) and argv[1:3] == ["pr", "merge"]:\n'
        '        return "gh pr merge"',
        '    if False:\n        return "gh pr merge"',
    ),
)

REAP = SCRIPTS / "reap.py"

REAP_MUTATIONS: Tuple[Mutation, ...] = (
    Mutation(
        "D53: the main checkout's own supervisor is no longer protected",
        '        if pid in guarded:\n            out.append(Target(pid, MAIN, command, main))\n'
        '            continue',
        '        if False:\n            out.append(Target(pid, MAIN, command, main))\n'
        '            continue',
    ),
    Mutation(
        "D169: the relative-path arm (arm two) is dropped, so `make server` is invisible again",
        '    if not cwd:\n        return False\n    for token in command.split():',
        '    if not cwd:\n        return False\n    for token in []:',
    ),
    Mutation(
        "a process placed under the checkout root is never judged OURS",
        '        inside = next((path for path in seen if _under(path, root)), "")\n'
        '        if inside:',
        '        inside = ""\n        if inside:',
    ),
)

# DROPPED, NAMED RATHER THAN SILENTLY OMITTED: a fourth reap.py mutation flipped the UNKNOWN
# verdict (a pid with no readable evidence) to GONE (nothing to judge). It SURVIVED —
# reap-selftest.sh never poses a case that actually resolves to UNKNOWN and checks the outcome;
# it only comments that the behaviour exists (line ~291: "a process carrying no absolute path
# in its argv is UNKNOWN and refused") and its one `lsof`-absent path is a SKIP, not an
# assertion. Keeping this arm in the table would make `python3 scripts/mutate-guards.py` fail
# on a real gap in a file this branch does not own (reap-selftest.sh), so it is left out BY
# NAME here rather than padding the count with an arm that proves nothing against the current
# suite. See the wrap-up report: this is a real finding for a session that owns
# scripts/reap-selftest.sh, not a bug in this file.

PRIMARY_SYNC = SCRIPTS / "primary_sync.py"

PRIMARY_SYNC_MUTATIONS: Tuple[Mutation, ...] = (
    Mutation(
        "D139/D158: a linked worktree is no longer exempt from being synced",
        '    if ports.is_linked_worktree(subject):\n        return _quiet("subject-is-linked")',
        '    if False:\n        return _quiet("subject-is-linked")',
    ),
    Mutation(
        "a dirty tracked tree is no longer refused (uncommitted work can be moved under)",
        '    if dirt:\n        shown = dirt[:10]',
        '    if False:\n        shown = dirt[:10]',
    ),
    Mutation(
        "main checked out in another worktree is no longer refused (main-elsewhere)",
        '    if branch != "main" and holder is not None:\n        return _refuse(\n'
        '            "main-elsewhere",',
        '    if False:\n        return _refuse(\n'
        '            "main-elsewhere",',
    ),
    Mutation(
        "a detached HEAD orphaned from every branch is no longer refused",
        '        if not contains.out.strip():\n            return _refuse(\n'
        '                "detached-orphan",',
        '        if False:\n            return _refuse(\n'
        '                "detached-orphan",',
    ),
    Mutation(
        "the fast-forward-only test always says yes, permitting a non-fast-forward move",
        '    elif _is_ancestor(subject, MAIN_REF, ORIGIN_MAIN_REF):\n        ff_needed = True',
        '    elif True:\n        ff_needed = True',
    ),
)

REVERT_AUDIT = SCRIPTS / "revert-audit.py"

REVERT_AUDIT_MUTATIONS: Tuple[Mutation, ...] = (
    Mutation(
        "the guard never runs once HEAD is at or behind upstream (never refuses at all)",
        '    if head_sha == up_sha or git_status(["merge-base", "--is-ancestor", head_sha, up_sha], cwd)[0] == 0:\n'
        '        print(f"revert guard: {head} is at or behind {upstream}; nothing would land.", file=out)\n'
        '        return 0',
        '    if True:\n'
        '        print(f"revert guard: {head} is at or behind {upstream}; nothing would land.", file=out)\n'
        '        return 0',
    ),
    Mutation(
        "a whole-file / all-hunks reversal is never classed as an unexplained refusal",
        '        elif h.entire:\n            refused.append(h)',
        '        elif False:\n            refused.append(h)',
    ),
    Mutation(
        "every reversal is treated as declared in the commit message (the refusal never fires)",
        '        if message_names(message, h.path):\n            declared.append(h)',
        '        if True:\n            declared.append(h)',
    ),
    Mutation(
        "the escape hatch fires even when it was not asked for",
        '    if os.environ.get(ESCAPE, "") == "off":',
        '    if True:',
    ),
)

MERGE_PR = SCRIPTS / "merge-pr.py"

# THE CLAIM COMMIT'S WAIT, and specifically its two-sided reading of mergeability. It is here
# rather than in a sentence because the second arm is the dangerous one: reading `UNKNOWN` as
# a conflict aborts EVERY merge this repo makes, and it is the natural way to write this
# wrong. See the wait's own section header in `scripts/merge-pr.py`.
MERGE_PR_MUTATIONS: Tuple[Mutation, ...] = (
    Mutation(
        "the wait never notices a branch that stopped being mergeable (PR #436, 2026-09-20)",
        '            if state == "CONFLICTING":',
        '            if False:',
    ),
    Mutation(
        "`UNKNOWN` is read as conflicted — which would abort every merge",
        '            if state == "CONFLICTING":',
        '            if state != "MERGEABLE":',
    ),
    Mutation(
        "an unreadable mergeability answer is read as a conflict",
        '            except Exception:                                 # noqa: BLE001 — no news\n'
        '                state = ""',
        '            except Exception:                                 # noqa: BLE001 — no news\n'
        '                state = "CONFLICTING"',
    ),
)

GUARDS: Tuple[GuardSpec, ...] = (
    GuardSpec("guard-shell-selftest", GUARD_SHELL, GUARD_SHELL_MUTATIONS,
              _sh_suite_runner("guard-shell.py", "guard-shell-selftest.sh")),
    GuardSpec("silent-write-selftest", SILENT_WRITE_GUARD, SILENT_WRITE_MUTATIONS,
              _sh_suite_runner("silent-write-guard.py", "silent-write-selftest.sh")),
    GuardSpec("reap-selftest", REAP, REAP_MUTATIONS,
              _sh_suite_runner("reap.py", "reap-selftest.sh")),
    GuardSpec("sync-selftest", PRIMARY_SYNC, PRIMARY_SYNC_MUTATIONS, _sync_suite_runner()),
    GuardSpec("revert-selftest", REVERT_AUDIT, REVERT_AUDIT_MUTATIONS,
              _revert_audit_suite_runner()),
    GuardSpec("claim-selftest", MERGE_PR, MERGE_PR_MUTATIONS,
              _py_suite_runner("merge-pr.py", "claim-selftest.py")),
)


# --------------------------------------------------------------------------------- verify-anchors


def verify_anchors(guards: Sequence[GuardSpec] = GUARDS) -> int:
    """Fast: no subprocess. Every mutation's anchor must appear EXACTLY ONCE in the guard's
    CURRENT source. Zero occurrences means the source moved on; more than one means the
    replacement is ambiguous about which occurrence it means to hit — the parent model's own
    `if old not in source` check, made stricter because `str.replace(old, new, 1)` silently
    picks the first of several and a mutation sweep should never be silently wrong about which
    line it broke.
    """
    problems: List[str] = []
    total = 0
    for guard in guards:
        source = guard.guard_path.read_text(encoding="utf-8")
        for mutation in guard.mutations:
            total += 1
            count = source.count(mutation.anchor)
            if count == 0:
                problems.append(
                    f"STALE  {guard.name}: {mutation.label!r} — anchor text not found in "
                    f"{guard.guard_path}")
            elif count > 1:
                problems.append(
                    f"AMBIGUOUS  {guard.name}: {mutation.label!r} — anchor text appears "
                    f"{count} times in {guard.guard_path}, replace(..., 1) would pick "
                    "whichever the file happens to list first")
    if problems:
        for line in problems:
            print("ERROR " + line)
        print()
        print(f"{len(problems)} of {total} anchors are stale or ambiguous.")
        return 1
    print(f"{total} of {total} anchors verified: every mutation's anchor text is present "
          "exactly once in the guard it targets.")
    return 0


# --------------------------------------------------------------------------------- the real run


def run_guard(guard: GuardSpec) -> Tuple[int, int]:
    """Run every mutation for one guard. Returns (survived, stale)."""
    source = guard.guard_path.read_text(encoding="utf-8")
    survived = 0
    stale = 0
    print(f"\n== {guard.name}  ({guard.guard_path.relative_to(ROOT)}, "
          f"{len(guard.mutations)} mutations) ==")
    for mutation in guard.mutations:
        if source.count(mutation.anchor) != 1:
            print(f"ERROR stale anchor, not found exactly once: {mutation.label}")
            stale += 1
            continue
        mutated = source.replace(mutation.anchor, mutation.replacement, 1)
        work = Path(tempfile.mkdtemp(prefix="mutate_guards_"))
        try:
            result = guard.prepare_and_run(work, mutated)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        fail_lines = [line for line in result.output.splitlines()
                     if "FAIL" in line or line.startswith("ERROR")]
        if result.returncode == 0:
            survived += 1
            print(f"SURVIVED  {mutation.label:<70} exit 0")
        else:
            print(f"KILLED    {mutation.label:<70} exit {result.returncode}, "
                  f"{len(fail_lines)} red line(s)")
    return survived, stale


def run_all(guards: Sequence[GuardSpec] = GUARDS) -> int:
    total_survived = 0
    total_stale = 0
    total_mutations = 0
    for guard in guards:
        survived, stale = run_guard(guard)
        total_survived += survived
        total_stale += stale
        total_mutations += len(guard.mutations)
    print()
    print(f"{total_mutations} mutations across {len(guards)} guards: "
          f"{total_mutations - total_survived - total_stale} killed, "
          f"{total_survived} survived, {total_stale} stale.")
    return 1 if (total_survived or total_stale) else 0


def print_counts(guards: Sequence[GuardSpec] = GUARDS) -> int:
    for guard in guards:
        print(f"{guard.name}: {len(guard.mutations)} arms")
    print(f"total: {sum(len(g.mutations) for g in guards)} arms across {len(guards)} guards")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verify-anchors", action="store_true",
                        help="fast: check every mutation's anchor is still present, no subprocess")
    parser.add_argument("--counts", action="store_true",
                        help="print the arm count per guard and exit; no subprocess")
    args = parser.parse_args(argv)

    started = time.monotonic()
    if args.counts:
        code = print_counts()
    elif args.verify_anchors:
        code = verify_anchors()
    else:
        code = run_all()
    elapsed = time.monotonic() - started
    print(f"\n({elapsed:.2f}s)")
    return code


if __name__ == "__main__":
    sys.exit(main())
