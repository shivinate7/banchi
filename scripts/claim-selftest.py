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

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAIMER = ROOT / "scripts" / "claim-ids.py"

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


def claim(repo: Path, *args: str) -> str:
    done = subprocess.run(
        [sys.executable, str(CLAIMER), "--root", str(repo)] + list(args),
        cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return done.stdout.decode("utf-8", errors="replace")


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

    print("\nclaim self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
