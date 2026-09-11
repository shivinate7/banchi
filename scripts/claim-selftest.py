#!/usr/bin/env python3
"""`scripts/claim-ids.py` proved against a throwaway repository (D140).

THE ALLOCATION IS THE PART THAT CANNOT BE ASSERTED ABOUT. Everything else in that script is
text substitution, and the one thing it must get right — allocating against what MAIN has
taken rather than against the branch's own copy — is only visible when main and the branch
disagree. So this builds a repository where they do: a branch takes three slugs, main takes
two numbers underneath it, and the claim has to land above both.

Every arm here is a REFUSAL or a MEASUREMENT, never a restatement of the code. In `make check`
and never in the git hook: it writes, into a directory it creates and destroys (D18).
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parent.parent
CLAIMER = ROOT / "scripts" / "claim-ids.py"
MERGER = ROOT / "scripts" / "merge-pr.py"


def merge_pr_module():
    """`scripts/merge-pr.py`, imported, so `claim_half` can be driven directly.

    IT NEVER REACHES `gh` IN PREVIEW. `claim_half`'s `if not confirm: return 0` sits above its
    first `gh` call, so every precondition in it is exercisable with no network, no pull
    request and no stub. Nothing drove this function before D143, which is the
    whole reason its precondition could sit seven lines out of place and look tested.
    """
    spec = importlib.util.spec_from_file_location("merge_pr", MERGER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def drive_claim_half(repo: Path, branch: str, number: int = 99) -> Tuple[str, int]:
    """`claim_half` in PREVIEW against `repo`, with everything it prints captured."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = merge_pr_module().claim_half(str(repo), number, branch, False)
    return buf.getvalue(), code


def with_claimer(repo: Path) -> None:
    """Put the claimer where `merge-pr.py` looks for it — `scripts/claim-ids.py`, RELATIVE to
    the checkout it is pointed at. A real tree has one; without it the readers below the
    precondition cannot run at all, and an arm would pass for the wrong reason."""
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(CLAIMER, repo / "scripts" / "claim-ids.py")

# THE FIXTURE'S IDS ARE COMPOSED, NEVER WRITTEN, on this repo's standing rule for test data.
# This file sits inside the auditor's own haystack, so a literal slug here IS a citation
# of an entry that does not exist, and `id claims` reports it — correctly, which is the point.
# Composing keeps the fixture out of the illustration problem docs/map.py records for `D2`.
# The numeric fixture ids are composed for the same reason as the slugs: `f"D{1}"` is data,
# `D1` written out is a citation of this repo's own first entry.
def D(n: int) -> str:
    return f"D{n}"


def C(n: int) -> str:
    return f"C{n}"


SD = "D-" + "third-thing"
SD_LONG = SD + "-again"
SC = "C-" + "second-code"
SS = "third" + "-step"

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print("  ok     {0}".format(label))
    else:
        FAIL += 1
        print("  FAIL   {0}".format(label))
        if detail:
            for line in str(detail).splitlines()[:8]:
                print("         {0}".format(line))


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t"] + list(args),
        cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return done.stdout.decode("utf-8", errors="replace")


def claim_rc(repo: Path, *args: str) -> Tuple[str, int]:
    """Output and EXIT CODE. The staleness half gates on the code, so a test that reads only
    the text cannot tell a refusal from a report — which is the arm, not a detail."""
    done = subprocess.run(
        [sys.executable, str(CLAIMER), "--root", str(repo)] + list(args),
        cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return done.stdout.decode("utf-8", errors="replace"), done.returncode


def claim(repo: Path, *args: str) -> str:
    return claim_rc(repo, *args)[0]


def write(repo: Path, name: str, body: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


# ------------------------------------------------------------------------------ the fixture


DECISIONS_MAIN = f"## {D(1)} — First\n\nbody\n\n## {D(2)} — Second\n\nbody\n"
CODES_MAIN = f"## {C(1)} — A code entry\n\nbody\n"
GATES_MAIN = "## What shipped\n\n1. ~~First step~~ — done.\n2. ~~Second step~~ — done.\n"
# THE MAP STORES A STEP ID BARE, which no `step <slug>` token can reach — the gap the
# bootstrap PR found by trying to claim its own step against a fixture that had no map.
MAP_MAIN = 'SHIPPED = [\n    {"n": 1, "title": "First"},\n    {"n": 2, "title": "Second"},\n]\n'


def build(tmp: Path) -> Path:
    origin = tmp / "origin.git"
    work = tmp / "work"
    seed = tmp / "seed"
    seed.mkdir()
    git(seed, "init", "-q", ".")
    write(seed, "docs/DECISIONS.md", DECISIONS_MAIN)
    write(seed, "docs/CODES-DECISIONS.md", CODES_MAIN)
    write(seed, "docs/GATES.md", GATES_MAIN)
    write(seed, "docs/map.py", MAP_MAIN)
    write(seed, "CLAUDE.md", f"# Fixture\n\nmain cites {D(2)} and step 2 and {C(1)}.\n")
    git(seed, "add", "-A")
    git(seed, "commit", "-qm", "seed")
    git(seed, "branch", "-M", "main")
    subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(origin)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    subprocess.run(["git", "clone", "-q", str(origin), str(work)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return work


def main() -> int:
    print("claim self-test — scripts/claim-ids.py against a throwaway repository\n")
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        work = build(tmp)

        print("  -- a branch writes slugs and cites them --")
        git(work, "checkout", "-q", "-b", "feature")
        write(work, "docs/DECISIONS.md",
              DECISIONS_MAIN + f"\n## {SD} — Third\n\nbody\n")
        write(work, "docs/CODES-DECISIONS.md",
              CODES_MAIN + f"\n## {SC} — Another\n\nbody\n")
        write(work, "docs/GATES.md",
              GATES_MAIN + f"0. `step {SS}` **Third step** — done.\n")
        write(work, "docs/map.py",
              MAP_MAIN.replace("]\n", '    {"n": "' + SS + '", "title": "Third"},\n]\n'))
        write(work, "CLAUDE.md",
              f"# Fixture\n\nmain cites {D(2)} and step 2 and {C(1)}.\n"
              f"the branch cites {SD}, {SC} and step {SS}.\n"
              f"and again: {SD} governs step {SS}.\n")
        git(work, "add", "-A")
        git(work, "commit", "-qm", "the branch writes its entries")

        out = claim(work, "--porcelain")
        ok(sorted(out.split("\n")) == sorted(
            [f"{SC}\t{C(2)}", f"{SD}\t{D(3)}", f"step {SS}\tstep 3", ""]),
           "each namespace allocates max+1 against main", out)

        print("\n  -- main moves underneath it, which is the whole point --")
        other = tmp / "other"
        subprocess.run(["git", "clone", "-q", str(tmp / "origin.git"), str(other)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        write(other, "docs/DECISIONS.md",
              DECISIONS_MAIN + f"\n## {D(3)} — Somebody else's third\n\nbody\n"
              f"\n## {D(4)} — And a fourth\n\nbody\n")
        write(other, "docs/GATES.md", GATES_MAIN + "3. ~~Somebody else's third step~~ — done.\n")
        git(other, "add", "-A")
        git(other, "commit", "-qm", "main takes 3 and 4")
        git(other, "push", "-q", "origin", "main")
        git(work, "fetch", "-q", "origin", "main")

        out = claim(work, "--porcelain")
        ok(f"{SD}\t{D(5)}" in out,
           "THE SAME BRANCH NOW CLAIMS ONE HIGHER — the allocation reads main, not the branch", out)
        ok(f"step {SS}\tstep 4" in out,
           "and the step follows main's own list, not the branch's copy of it", out)
        ok(f"{SC}\t{C(2)}" in out,
           "while a namespace main did not touch is unmoved", out)

        print("\n  -- preview writes nothing --")
        before = (work / "CLAUDE.md").read_text(encoding="utf-8")
        claim(work)
        ok((work / "CLAUDE.md").read_text(encoding="utf-8") == before,
           "a bare run is a preview and leaves every file alone")

        print("\n  -- --write substitutes every citation, in every file --")
        claim(work, "--write")
        claude = (work / "CLAUDE.md").read_text(encoding="utf-8")
        ok(SD not in claude and SC not in claude and SS not in claude,
           "no slug survives in the prose", claude)
        ok(claude.count(D(5)) == 2, "BOTH citations of the entry moved, not the first",
           claude)
        ok("step 4" in claude and C(2) in claude,
           "and the other two namespaces with it", claude)
        ok(f"main cites {D(2)} and step 2 and {C(1)}." in claude,
           "while main's own citations are untouched — the token is the branch's alone",
           claude)

        gates = (work / "docs/GATES.md").read_text(encoding="utf-8")
        ok(re.search(r"^4\. \*\*Third step\*\*", gates, re.M) is not None,
           "the `0.` marker became the allocated number, which is the one edit that is not "
           "a token substitution", gates)
        ok("0." not in gates.split("\n")[-2],
           "and no pending marker is left behind", gates)
        ok((work / "docs/DECISIONS.md").read_text(encoding="utf-8").count("## " + D(5) + " — Third") == 1,
           "the heading itself carries the number now")

        # THE MAP'S `n` IS THE SECOND NON-TOKEN EDIT, and it must land as an INTEGER:
        # `build order mirror` reads GATES.md's markers with int() and compares by equality,
        # so a quoted "4" agrees with nothing. Missing entirely until the bootstrap PR.
        mapped = (work / "docs/map.py").read_text(encoding="utf-8")
        ok('{"n": 4, "title": "Third"}' in mapped,
           "the map's bare `n` field takes the number too, as an int and not a string", mapped)
        ok(SS not in mapped, "and no slug is left in the map", mapped)

        print("\n  -- it is idempotent, because there is nothing left to find --")
        again = claim(work, "--porcelain")
        ok(again.strip() == "", "a second run claims nothing", again)

        print("\n  -- one slug is not allowed to be eaten by another --")
        # One fixture slug is a PREFIX of the other. An unbounded substitution
        # rewrites the shorter inside the longer and leaves a number with a tail
        # on it, which resolves to nothing and reads like a typo rather than a tool's bug.
        third = tmp / "third"
        third.mkdir()
        prefixed = build(third)
        git(prefixed, "checkout", "-q", "-b", "feature")
        write(prefixed, "docs/DECISIONS.md", DECISIONS_MAIN
              + f"\n## {SD} — Short\n\nbody\n"
              + f"\n## {SD_LONG} — Long\n\nbody\n")
        write(prefixed, "CLAUDE.md",
              f"# Fixture\n\ncites {SD} and {SD_LONG}.\n")
        git(prefixed, "add", "-A")
        git(prefixed, "commit", "-qm", "two slugs, one a prefix of the other")
        claim(prefixed, "--write")
        body = (prefixed / "CLAUDE.md").read_text(encoding="utf-8")
        ok(f"cites {D(3)} and {D(4)}." in body,
           "a slug that is a prefix of another is substituted whole, not inside it", body)

        print("\n  -- refusals --")
        out = claim(work, "--ref", "origin/does-not-exist")
        ok("REFUSED" in out and "does not name a commit" in out,
           "a ref that does not resolve is refused, not guessed past", out)

        print("\n  -- a slug that is one segment is not an id, and is left alone --")
        second = tmp / "second"
        second.mkdir()
        fresh = build(second)
        write(fresh, "docs/DECISIONS.md", DECISIONS_MAIN + "\n## D-pad — Not an id\n\nbody\n")
        git(fresh, "add", "-A")
        git(fresh, "commit", "-qm", "a one-segment heading")
        out = claim(fresh, "--porcelain")
        ok(out.strip() == "",
           "a one-segment heading allocates nothing — one segment is prose, and docs-audit's `id claims` "
           "row is what reports the heading as unreachable", out)


        # -------------------------------------------- D140, amended 2026-09-11: staleness
        # THE CLAIMER IS A NO-OP ONCE A BRANCH HAS CLAIMED, so every arm above goes green on a
        # branch whose number main has since taken. These build that branch. It happened twice
        # on 2026-09-11 — #262/#265 on one number, #265/#270 on the next — and a person reading
        # PR titles was the only thing that caught either.
        print("\n  -- a branch claims honestly, and main takes the number afterwards --")
        fourth = tmp / "fourth"
        fourth.mkdir()
        late = build(fourth)
        git(late, "checkout", "-q", "-b", "feature")
        # Honest at the time: main holds 1 and 2 in all three namespaces, so these are free.
        write(late, "docs/DECISIONS.md",
              DECISIONS_MAIN + f"\n## {D(3)} — The branch's third\n\nbody\n")
        write(late, "docs/CODES-DECISIONS.md",
              CODES_MAIN + f"\n## {C(2)} — The branch's code entry\n\nbody\n")
        write(late, "docs/GATES.md", GATES_MAIN + "3. ~~The branch's third step~~ — done.\n")
        git(late, "add", "-A")
        git(late, "commit", "-qm", "the branch claims its numbers")

        out, code = claim_rc(late, "--stale")
        ok(code == 0 and "nothing has gone stale" in out,
           "while main has not moved, an honestly claimed number reports clean", out)

        rival = fourth / "rival"
        subprocess.run(["git", "clone", "-q", str(fourth / "origin.git"), str(rival)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        write(rival, "docs/DECISIONS.md",
              DECISIONS_MAIN + f"\n## {D(3)} — Somebody else's third\n\nbody\n")
        write(rival, "docs/CODES-DECISIONS.md",
              CODES_MAIN + f"\n## {C(2)} — Somebody else's code entry\n\nbody\n")
        write(rival, "docs/GATES.md", GATES_MAIN + "3. ~~Somebody else's third step~~ — done.\n")
        git(rival, "add", "-A")
        git(rival, "commit", "-qm", "main takes the same three")
        git(rival, "push", "-q", "origin", "main")
        git(late, "fetch", "-q", "origin", "main")

        print("\n  -- and now the claimed number is stale, in all three namespaces --")
        out, code = claim_rc(late, "--stale")
        ok(code == 3, "it exits non-zero, so it can gate", f"exit={code}\n{out}")
        ok("REFUSED" in out,
           "THE BRANCH IS NO LONGER A NO-OP — a claimed number main has since taken is "
           "reported, where the claimer alone says `nothing to do`", out)
        ok(f"{D(3)}" in out and f"{D(4)}" in out,
           "the decision is named, with what it would become", out)
        ok(f"{C(2)}" in out and f"{C(3)}" in out, "the code-card namespace too", out)
        ok("step 3" in out and "step 4" in out, "and the build step", out)
        ok(out.count("is taken on") == 3,
           "EXACTLY the three it added — the ids main already held are in the branch's copy "
           "too, and reporting those would report most of the file", out)

        print("\n  -- the refusal reaches the writing path, and writes nothing --")
        before = (late / "docs/DECISIONS.md").read_text(encoding="utf-8")
        out, code = claim_rc(late, "--write")
        ok(code == 3 and "REFUSED" in out,
           "`--write` refuses as well, not only `--stale`", out)
        ok((late / "docs/DECISIONS.md").read_text(encoding="utf-8") == before,
           "and nothing was rewritten — a half-performed claim would leave the branch "
           "carrying a fresh number and a stale one in one commit")

        print("\n  -- `--porcelain` keeps its contract, which is load-bearing --")
        out, code = claim_rc(late, "--porcelain")
        ok(code == 0,
           "`--porcelain` still exits 0 on a stale tree. scripts/merge-pr.py reads a non-zero "
           "exit there as `no claims are pending` and would SKIP the claim silently — the "
           "opposite of a guard. It asks for `--stale` in its own right instead", out)

        print("\n  -- a hole is not a collision --")
        # D80 culls step 12 and keeps the gap, so `free` is set membership and never `above
        # the ceiling`. A branch holding an id BELOW main's highest that main does not hold
        # is correct, and rewriting this check as a `>` comparison would refuse it.
        fifth = tmp / "fifth"
        fifth.mkdir()
        hole = build(fifth)
        git(hole, "checkout", "-q", "-b", "feature")
        write(hole, "docs/DECISIONS.md",
              DECISIONS_MAIN + f"\n## {D(3)} — The branch's third\n\nbody\n")
        git(hole, "add", "-A")
        git(hole, "commit", "-qm", "the branch takes three")
        skipper = fifth / "skipper"
        subprocess.run(["git", "clone", "-q", str(fifth / "origin.git"), str(skipper)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        write(skipper, "docs/DECISIONS.md",
              DECISIONS_MAIN + f"\n## {D(4)} — Main's fourth, with three left as a hole\n\nbody\n")
        git(skipper, "add", "-A")
        git(skipper, "commit", "-qm", "main takes four and leaves three")
        git(skipper, "push", "-q", "origin", "main")
        git(hole, "fetch", "-q", "origin", "main")
        out, code = claim_rc(hole, "--stale")
        ok(code == 0 and "nothing has gone stale" in out,
           "an id BELOW main's highest that main does not hold is free, and is not refused — "
           "the question is membership, never a comparison against the ceiling", out)

        print("\n  -- the two halves disagree about a missing ref, on purpose --")
        out, code = claim_rc(late, "--stale", "--ref", "origin/does-not-exist")
        ok(code == 0 and "ALLOWED" in out,
           "`--stale` ALLOWS where the claim refuses: it is in `make check`, which runs in "
           "clones that carry no remote-tracking branch, and a question it cannot be asked "
           "is not a failure", out)
        out, code = claim_rc(late, "--ref", "origin/does-not-exist")
        ok(code == 2 and "REFUSED" in out,
           "while the CLAIM still refuses the same ref — allocating against nothing is the "
           "guess D140 exists to delete", out)

        print("\n  -- mid-merge there is nothing to check yet --")
        # THE DOCUMENTED PRE-MERGE STEP PRODUCES THIS: fetch, merge origin/main, resolve,
        # push. The tree holds the other side's entries while the merge base has not moved,
        # so every id that merge brought in reads as this branch's own.
        eighth = tmp / "eighth"
        eighth.mkdir()
        mid = build(eighth)
        git(mid, "checkout", "-q", "-b", "feature")
        write(mid, "docs/DECISIONS.md", DECISIONS_MAIN + f"\n## {SD} — Third\n\nbody\n")
        git(mid, "add", "-A")
        git(mid, "commit", "-qm", "the branch writes a slug")
        other2 = eighth / "other"
        subprocess.run(["git", "clone", "-q", str(eighth / "origin.git"), str(other2)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        write(other2, "docs/DECISIONS.md",
              DECISIONS_MAIN + f"\n## {D(3)} — main's own third\n\nbody\n")
        git(other2, "add", "-A")
        git(other2, "commit", "-qm", "main takes three")
        git(other2, "push", "-q", "origin", "main")
        git(mid, "fetch", "-q", "origin", "main")
        conflicted = git(mid, "merge", "origin/main")
        out, code = claim_rc(mid, "--stale")
        ok(code == 0 and "merge is in progress" in out,
           "a tree mid-merge is ALLOWED rather than told to un-claim an id that belongs to "
           "the work it is merging in", out + "\n" + conflicted)

        print("\n  -- with no shared commit there is no baseline, and it refuses --")
        git(hole, "checkout", "-q", "--orphan", "unrelated")
        write(hole, "docs/DECISIONS.md", DECISIONS_MAIN)
        git(hole, "add", "-A")
        git(hole, "commit", "-qm", "an unrelated history")
        out, code = claim_rc(hole, "--stale")
        ok(code == 2 and "share no commit" in out,
           "a branch sharing no commit with the ref is refused rather than measured against "
           "nothing, which would report every id main holds as a collision", out)


        # ----------------------------------- D143: which tree is being read
        # THE PRECONDITION WAS SEVEN LINES TOO LATE, and every test stood in the right place,
        # so nothing saw it. On 2026-09-11 `make merge` was run from the primary checkout
        # standing on `main`: the claim half read MAIN, found no slug in it, printed
        # `nothing to claim`, and merged the pull request's slug onto main verbatim.
        print("\n  -- the claim half is pointed at a tree that is not the PR's --")
        sixth = tmp / "sixth"
        sixth.mkdir()
        tree = build(sixth)
        with_claimer(tree)
        git(tree, "add", "-A")
        git(tree, "commit", "-qm", "the checkout carries the claimer, as a real one does")
        git(tree, "checkout", "-q", "-b", "feature")
        write(tree, "docs/DECISIONS.md", DECISIONS_MAIN + f"\n## {SD} — Third\n\nbody\n")
        git(tree, "add", "-A")
        git(tree, "commit", "-qm", "the branch writes a slug")

        out, code = drive_claim_half(tree, "feature")
        ok(code == 0 and "REFUSED" not in out,
           "standing ON the PR's branch, the claim half proceeds — the precondition does not "
           "over-refuse", out)

        git(tree, "checkout", "-q", "main")
        module = merge_pr_module()
        ok(module.claims_pending(str(tree)) == [],
           "`main` really does have nothing pending, which is the condition that made the old "
           "ordering return 0 before it ever reached the precondition",
           str(module.claims_pending(str(tree))))

        out, code = drive_claim_half(tree, "feature")
        ok(code != 0 and "REFUSED" in out,
           "THE DEFECT: from `main`, with the slug on the PR's branch and nothing pending in "
           "`main` itself, the claim half REFUSES instead of reporting `nothing to claim`",
           out)
        ok("main" in out and "feature" in out,
           "and it names both trees — the one it stands in and the one it should be in", out)

        out, code = drive_claim_half(tree, "")
        ok(code != 0 and "did not report a head branch" in out,
           "a pull request with no head branch is refused rather than compared against an "
           "empty string, which would match no tree and refuse for the wrong reason", out)

        print("\n  -- and the staleness reader is no longer blind from the wrong tree --")
        # #272 closed "an allocated id can go stale". It reads the CHECKED-OUT TREE, so from
        # `main` it computed "what does this tree add over its merge base" — nothing — and
        # reported clean while the branch's stale number sat there. Fixing the claim alone
        # would have left that green row asserting something nobody had checked.
        seventh = tmp / "seventh"
        seventh.mkdir()
        blind = build(seventh)
        with_claimer(blind)
        git(blind, "add", "-A")
        git(blind, "commit", "-qm", "the checkout carries the claimer")
        git(blind, "checkout", "-q", "-b", "feature")
        write(blind, "docs/DECISIONS.md",
              DECISIONS_MAIN + f"\n## {D(3)} — claimed honestly at the time\n\nbody\n")
        git(blind, "add", "-A")
        git(blind, "commit", "-qm", "the branch claims a number")
        rival2 = seventh / "rival"
        subprocess.run(["git", "clone", "-q", str(seventh / "origin.git"), str(rival2)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        write(rival2, "docs/DECISIONS.md",
              DECISIONS_MAIN + f"\n## {D(3)} — main takes it afterwards\n\nbody\n")
        git(rival2, "add", "-A")
        git(rival2, "commit", "-qm", "main takes the same number")
        git(rival2, "push", "-q", "origin", "main")
        git(blind, "fetch", "-q", "origin", "main")

        out, code = drive_claim_half(blind, "feature")
        ok(code != 0 and "gone stale" in out,
           "standing on the branch, the stale number is caught — #272's guard, unchanged", out)

        git(blind, "checkout", "-q", "main")
        bare, _ = claim_rc(blind, "--stale")
        ok("nothing has gone stale" in bare,
           "READ FROM `main` THE STALENESS CHECK STILL SAYS CLEAN — it asks about the tree it "
           "is in, which is correct for `make claim-stale` and useless for a merge", bare)
        out, code = drive_claim_half(blind, "feature")
        ok(code != 0 and "REFUSED" in out and "gone stale" not in out,
           "so the CLAIM HALF refuses on the tree instead, before that clean answer can be "
           "used — one fix covering both holes, at the point where the pointing happens", out)

        # AND THE PRECONDITION SITS ABOVE THE STALENESS READ, not merely above the pending
        # check. Standing on a DIFFERENT branch that itself holds a stale number, a run that
        # read staleness first would refuse with a true sentence about THIS tree while naming
        # a pull request it is not merging — a refusal that sends the reader to the wrong
        # branch. The tree is established first, so the message is about the tree.
        git(blind, "checkout", "-q", "feature")
        out, code = drive_claim_half(blind, "some-other-branch")
        ok(code != 0 and "some-other-branch" in out and "gone stale" not in out,
           "standing on a stale branch while merging a DIFFERENT pull request refuses about "
           "the TREE, not about this tree's staleness — the precondition is above the "
           "staleness read and not only above the pending check", out)

    print("\nclaim self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
