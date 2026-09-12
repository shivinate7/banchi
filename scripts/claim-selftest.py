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
import json
import os
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


def drive_landed_half(repo: Path, commit: str) -> Tuple[str, int]:
    """`landed_half` against `repo`, with everything it prints captured.

    IT PRESSES NOTHING AND NEEDS NO `gh`. The half runs after main has already moved, so its
    whole body is one read of a commit — which is exactly why it can be driven here while the
    merge around it cannot.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = merge_pr_module().landed_half(str(repo), commit)
    return buf.getvalue(), code


def with_claimer(repo: Path) -> None:
    """Put the claimer where `merge-pr.py` looks for it — `scripts/claim-ids.py`, RELATIVE to
    the checkout it is pointed at. A real tree has one; without it the readers below the
    precondition cannot run at all, and an arm would pass for the wrong reason."""
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(CLAIMER, repo / "scripts" / "claim-ids.py")
    # AND THE TWO THE CLAIM STEP REACHES FOR. `settle_corpus` writes the manifest and the
    # index through these, and it is written to survive their absence — so a fixture without
    # them would exercise the SURVIVAL path on every arm and never the settling one, which is
    # a self-test passing for the wrong reason.
    for helper in ("decisions_corpus.py", "index-decisions.py"):
        source = CLAIMER.parent / helper
        if source.exists():
            shutil.copy(source, repo / "scripts" / helper)

# ------------------------------------------------- driving the wait for the claim commit
#
# THE WAIT IS THE ONE PART OF `claim_half` THAT PREVIEW CANNOT REACH, so everything below
# runs it with `confirm=True` against the throwaway origin — a real claim, a real commit, a
# real push — and a FAKE `gh` on PATH. Stubbing the function would prove the loop and say
# nothing about the question it asks, and the question is the whole defect.


class Clock:
    """A monotonic clock that only moves when the code under test sleeps.

    The deadline is forty-five minutes and a poll is ten seconds; on a real clock the
    deadline arm is untestable and the settle arm is slow. On this one both are instant and
    the constants under test stay at their shipped values.
    """

    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds or 1.0


class Scripted:
    """A check-run reader answering from a list — one reading per call, holding the last."""

    def __init__(self, *steps) -> None:
        self.steps = list(steps)
        self.asked: list = []

    def __call__(self, sha):
        self.asked.append(sha)
        return self.steps[min(len(self.asked) - 1, len(self.steps) - 1)]


def reading(module, *runs, ok: bool = True, err: str = ""):
    """A `Reading` in the shape `read_check_runs` returns — sorted, three fields per run."""
    return module.Reading(ok, tuple(sorted(runs)), err)


def done(name: str, conclusion: str = "success"):
    return (name, "completed", conclusion)


def running(name: str):
    return (name, "in_progress", "")


# THE FAKE `gh` ANSWERS BOTH QUESTIONS, AND THAT IS THE POINT. `gh pr checks <n>` answers
# green and instantly, the way the real one does off the PREVIOUS head's runs the moment a
# claim commit is pushed. The SHA-pinned endpoint answers from a script. A wait that asks
# the wrong question therefore PASSES here, loudly and wrongly, which is what makes the
# mutation that restores it turn an arm red instead of merely slower.
FAKE_GH = '''#!/usr/bin/env python3
import json, os, re, sys

home = os.environ["FAKE_GH_DIR"]
argv = sys.argv[1:]
with open(os.path.join(home, "calls.log"), "a") as fh:
    fh.write(" ".join(argv) + "\\n")

if argv[:2] == ["pr", "checks"]:
    print("All checks were successful")
    sys.exit(0)

if argv[:1] == ["api"]:
    found = re.search(r"commits/([^/?]+)/check-runs", " ".join(argv))
    if not found:
        sys.stderr.write("fake gh: not a check-runs question: " + " ".join(argv) + "\\n")
        sys.exit(1)
    sha = found.group(1)
    book = os.path.join(home, sha + ".json")
    if not os.path.exists(book):
        book = os.path.join(home, "default.json")
    with open(book) as fh:
        steps = json.load(fh)
    tally = os.path.join(home, sha + ".seen")
    n = int(open(tally).read()) if os.path.exists(tally) else 0
    with open(tally, "w") as fh:
        fh.write(str(n + 1))
    runs = steps[min(n, len(steps) - 1)]
    if runs is None:
        sys.stderr.write("gh: No commit found for SHA: " + sha + " (HTTP 422)\\n")
        sys.exit(1)
    print(json.dumps({"total_count": len(runs), "check_runs": runs}))
    sys.exit(0)

sys.stderr.write("fake gh: unscripted " + " ".join(argv) + "\\n")
sys.exit(1)
'''


class FakeGh:
    """A `gh` on PATH, with a scripted answer per commit and a log of every question."""

    def __init__(self, home: Path) -> None:
        self.home = home
        (home / "bin").mkdir(parents=True, exist_ok=True)
        exe = home / "bin" / "gh"
        exe.write_text(FAKE_GH, encoding="utf-8")
        exe.chmod(0o755)
        self.script("default", [[]])

    def script(self, sha: str, steps) -> None:
        """`steps[n]` is the answer to the n-th question about `sha`; the last one holds."""
        (self.home / (sha + ".json")).write_text(
            json.dumps([None if s is None else
                        [{"name": n, "status": st, "conclusion": c} for n, st, c in s]
                        for s in steps]), encoding="utf-8")

    def calls(self) -> list:
        log = self.home / "calls.log"
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []

    def __enter__(self):
        self.was = dict(os.environ)
        os.environ["PATH"] = str(self.home / "bin") + os.pathsep + os.environ.get("PATH", "")
        os.environ["FAKE_GH_DIR"] = str(self.home)
        return self

    def __exit__(self, *_):
        os.environ.clear()
        os.environ.update(self.was)
        return False


def waitable(deadline: float = 0):
    """`scripts/merge-pr.py` with its poll shortened, and optionally its deadline.

    THE ARMS THAT DRIVE THE LOOP LEAVE THE DEADLINE AT ITS SHIPPED VALUE and move a fake
    clock instead, so the forty-five minutes is the forty-five minutes that ships. The arms
    that drive the whole claim half cannot inject a clock — `claim_half` builds its own —
    so they take a short real one, which bounds a BROKEN fixture rather than proving
    anything about the constant: with the poll at zero, a `gh` that cannot be run spins for
    three quarters of an hour and reads as a hung test.
    """
    module = merge_pr_module()
    module.CHECK_POLL_SECONDS = 0
    if deadline:
        module.CHECK_DEADLINE_SECONDS = deadline
    return module


def quietly(fn, *args, **kw):
    """Run it with its progress swallowed. The wait prints a heartbeat a minute and the
    fake clock spends forty-five of them in a blink, which is 45 lines per arm of a stream
    that exists for a human watching one real run."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        got = fn(*args, **kw)
    return got


def signable(repo: Path) -> None:
    """`claim_half` commits with a plain `git commit`, so the identity has to be in config."""
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(repo), check=False)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(repo), check=False)


def drive_claim_commit(module, repo: Path, branch: str, number: int = 99) -> Tuple[str, int]:
    """`claim_half` with `confirm=True` — the claim, the commit, the push and the wait."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = module.claim_half(str(repo), number, branch, True)
    return buf.getvalue(), code


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


        # ------------------------------- the wait, and what it is a wait FOR
        # TWO DEFECTS, AND THE SECOND IS THE WORSE ONE. The wait called
        # `gh pr checks <n>`, which asks about a PULL REQUEST: right after the claim commit
        # is pushed GitHub has attached nothing to the new head, so that question is answered
        # out of the PREVIOUS head's runs and exits 0 at once. It has to see the OLD head
        # green to be silent, which is why nothing noticed. And pinning to the SHA does not
        # fix it on its own — a commit with nothing attached yet answers with an EMPTY list,
        # and "zero pending" read off an empty list is the same sentence as "all passed".
        # Both were measured on live merges on 2026-09-11: #275 merged while its claim
        # commit's own run was `in_progress`, #277 with four of seven still running, and a
        # watcher reported #277 SETTLED off an empty answer.
        print("\n  -- a complete roster goes green, and only after a second look --")
        module = waitable()
        eyes = Scripted(reading(module, done("check"), done("revert-guard")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks,"abc1234", 99, 0, eyes, watch.sleep, watch.now)
        ok(green, "a non-empty, complete, unchanging roster passes", "\n".join(lines))
        ok(len(eyes.asked) == 2,
           "and it read TWICE before saying so — one complete reading is `nothing is running "
           "right now`, which is not the same as `nothing more is coming`",
           str(len(eyes.asked)))
        ok(eyes.asked == ["abc1234", "abc1234"],
           "every question was about the COMMIT it was handed", str(eyes.asked))

        print("\n  -- ABSENCE IS NOT A PASS, which is the defect that cost the most --")
        eyes = Scripted(reading(module))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks,"abc1234", 99, 0, eyes, watch.sleep, watch.now)
        ok(not green,
           "a commit GitHub has attached NOTHING to never goes green, however many times it "
           "is asked — zero pending is not zero checks", "\n".join(lines))
        ok("no check run is attached" in "\n".join(lines),
           "and it says which of the two it saw, so the reader is not left to guess whether "
           "CI is broken or slow", "\n".join(lines))
        ok(watch.now() >= module.CHECK_DEADLINE_SECONDS,
           "it spent the whole deadline asking again rather than concluding", str(watch.now()))

        print("\n  -- an empty first answer is a `not yet`, not a verdict --")
        eyes = Scripted(reading(module), reading(module, done("check")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks,"abc1234", 99, 0, eyes, watch.sleep, watch.now)
        ok(green and len(eyes.asked) == 3,
           "the empty reading was waited through and the roster that followed was the one it "
           "concluded from", "\n".join(lines) + "\nasked " + str(len(eyes.asked)))

        print("\n  -- an unreadable answer is not an empty one, and neither is green --")
        eyes = Scripted(reading(module, ok=False, err="gh: HTTP 502"))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks,"abc1234", 99, 0, eyes, watch.sleep, watch.now)
        ok(not green and "cannot be read" in "\n".join(lines),
           "a read that FAILED carries no runs either, and a wait that treated the two alike "
           "would pass every time GitHub was down", "\n".join(lines))

        print("\n  -- a run still going holds it, and a failed one ends it at once --")
        eyes = Scripted(reading(module, done("check"), running("design-check (1)")),
                        reading(module, done("check"), done("design-check (1)")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks,"abc1234", 99, 0, eyes, watch.sleep, watch.now)
        ok(green and len(eyes.asked) == 3,
           "an `in_progress` run is waited for — #277 merged with four of these", str(len(eyes.asked)))

        eyes = Scripted(reading(module, done("check", "failure"), done("revert-guard")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks,"abc1234", 99, 0, eyes, watch.sleep, watch.now)
        ok(not green and len(eyes.asked) == 1 and "did not pass" in "\n".join(lines),
           "a failed conclusion refuses on the FIRST reading — the `--fail-fast` the old "
           "watch had, kept", "\n".join(lines))

        print("\n  -- skipped and neutral are not failures --")
        # D141 skips the browser matrix when a change reaches nothing a browser draws, and
        # D136 skips a tree that has already passed. Both land here as completed check runs.
        eyes = Scripted(reading(module, done("design-check", "skipped"),
                                done("already-passed", "neutral"), done("check")))
        watch = Clock()
        green, _ = quietly(module.wait_for_checks,"abc1234", 99, 0, eyes, watch.sleep, watch.now)
        ok(green, "a roster of skipped and neutral runs is complete, not failed")

        print("\n  -- the floor: a roster smaller than the parent's is still filling --")
        eyes = Scripted(reading(module, done("already-passed")),
                        reading(module, done("already-passed"), done("check"),
                                done("revert-guard")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks,"abc1234", 99, 3, eyes, watch.sleep, watch.now)
        ok(green and len(eyes.asked) == 3,
           "one green check out of the three the parent carried is not an answer — this is "
           "the shape #275 would have merged on if its own run had been slower to attach",
           "\n".join(lines) + "\nasked " + str(len(eyes.asked)))
        eyes = Scripted(reading(module, done("already-passed")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks,"abc1234", 99, 3, eyes, watch.sleep, watch.now)
        ok(not green and "parent commit carried 3" in "\n".join(lines),
           "and a roster that never fills to the floor RUNS OUT rather than passing, naming "
           "the shortfall", "\n".join(lines))

        print("\n  -- a roster that grows between two complete reads is not settled --")
        eyes = Scripted(reading(module, done("check")),
                        reading(module, done("check"), done("revert-guard")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks,"abc1234", 99, 0, eyes, watch.sleep, watch.now)
        ok(green and len(eyes.asked) == 3,
           "the first complete reading was not concluded from, because the next one was "
           "bigger — the settle is what catches a workflow GitHub dispatches late",
           str(len(eyes.asked)))

        print("\n  -- the deadline refuses, and names the commit --")
        eyes = Scripted(reading(module, running("check")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks,"deadbeefcafe", 271, 0, eyes, watch.sleep, watch.now)
        ok(not green and "gave up" in "\n".join(lines) and "deadbeefcafe" in "\n".join(lines),
           "a wait that never ends is a REFUSAL naming the claim commit, never a pass and "
           "never a hang", "\n".join(lines))

        print("\n  -- the reader itself, against a `gh` that answers and one that cannot --")
        # EVERY ARM ABOVE HANDS `wait_for_checks` A READING, so none of them can see how a
        # reading is MADE. `read_check_runs` is where the two kinds of nothing are told apart,
        # and collapsing them there is invisible to a stub: an unreadable answer carries no
        # runs, and a wait that read it as an empty one would pass every time GitHub is down.
        reader = tmp / "reader"
        reader.mkdir()
        bench = FakeGh(reader / "gh")
        bench.script("cafe0001", [[done("check"), running("design-check (1)")]])
        bench.script("cafe0002", [None])
        module = waitable()
        with bench:
            spoke = module.read_check_runs("cafe0001")
            mute = module.read_check_runs("cafe0002")
        ok(spoke.ok and spoke.runs == (("check", "completed", "success"),
                                       ("design-check (1)", "in_progress", "")),
           "an answered question yields one (name, status, conclusion) per run, sorted — "
           "GitHub's own order is not stable across reads and the settle compares readings "
           "for equality", str(spoke))
        ok(not mute.ok and not mute.runs and "422" in mute.err,
           "AND A QUESTION `gh` COULD NOT ANSWER IS `ok=False`, NEVER AN EMPTY ANSWER. Both "
           "carry no runs; only one of them is a fact about the commit", str(mute))

        print("\n  -- and now the whole claim half, with a fake `gh` on PATH --")
        # THE LOOP ABOVE IS NOT THE DEFECT; THE QUESTION IS. These arms run the real
        # `claim_half` — real claimer, real commit, real push to the throwaway origin — and
        # let it build its own `gh` argv. The fake answers `gh pr checks` GREEN AND INSTANTLY,
        # exactly as the real one does off the previous head, so a wait that asks the pull
        # request passes here rather than merely behaving differently.
        ninth = tmp / "ninth"
        ninth.mkdir()
        watched = build(ninth)
        with_claimer(watched)
        signable(watched)
        git(watched, "add", "-A")
        git(watched, "commit", "-qm", "the checkout carries the claimer")
        git(watched, "checkout", "-q", "-b", "feature")
        write(watched, "docs/DECISIONS.md", DECISIONS_MAIN + f"\n## {SD} — Third\n\nbody\n")
        git(watched, "add", "-A")
        git(watched, "commit", "-qm", "the branch writes a slug")
        before = git(watched, "rev-parse", "HEAD").strip()

        fake = FakeGh(ninth / "gh")
        # The parent — the PRE-CLAIM head, whose checks are the ones `gh pr checks` answers
        # out of — is complete and green, and carries three runs.
        fake.script(before, [[done("check"), done("revert-guard"), done("browser-scope")]])
        # The claim commit itself is still running when the wait first looks.
        fake.script("default", [
            [done("check"), running("revert-guard"), running("browser-scope")],
            [done("check"), done("revert-guard"), done("browser-scope")],
        ])
        with fake:
            out, code = drive_claim_commit(waitable(deadline=20), watched, "feature")
        after = git(watched, "rev-parse", "HEAD").strip()
        asked = fake.calls()

        ok(code == 0, "the claim half completes: claim, commit, push, wait", out)
        ok(any(after in line and line.startswith("api ") for line in asked),
           "THE WAIT ASKED ABOUT THE CLAIM COMMIT'S OWN SHA — the commit the substitution is "
           "in, which is what `gh pr checks <n>` never names", "\n".join(asked))
        ok(not any(line.startswith("pr checks") for line in asked),
           "AND IT NEVER ASKED THE PULL REQUEST. That question answers green and instantly "
           "out of the previous head, which is why two live merges went out unwatched",
           "\n".join(asked))
        ok(before != after and sum(1 for line in asked if after in line) >= 3,
           "it read the claim commit more than once — the `in_progress` answer did not end "
           "the wait, and the complete one was confirmed", "\n".join(asked))
        ok(any(before in line for line in asked),
           "and it read the PARENT once, for the floor: how many runs the pre-claim head "
           "carried is the only free lower bound on how many this one will",
           "\n".join(asked))

        print("\n  -- the same half, against a commit `gh` reports nothing for --")
        tenth = tmp / "tenth"
        tenth.mkdir()
        silent = build(tenth)
        with_claimer(silent)
        signable(silent)
        git(silent, "add", "-A")
        git(silent, "commit", "-qm", "the checkout carries the claimer")
        git(silent, "checkout", "-q", "-b", "feature")
        write(silent, "docs/DECISIONS.md", DECISIONS_MAIN + f"\n## {SD} — Third\n\nbody\n")
        git(silent, "add", "-A")
        git(silent, "commit", "-qm", "the branch writes a slug")

        quiet = FakeGh(tenth / "gh")
        quiet.script("default", [[]])
        module = waitable(deadline=0.5)
        with quiet:
            out, code = drive_claim_commit(module, silent, "feature")
        ok(code != 0 and "REFUSED" in out,
           "WITH NOTHING ATTACHED TO THE CLAIM COMMIT THE MERGE IS REFUSED. A watcher read "
           "this exact answer on #277 and called it settled, which would have merged a "
           "commit carrying no checks at all", out)
        ok("no check run is attached" in out or "gave up" in out,
           "and the refusal says the checks are not KNOWN rather than not green", out)

        print("\n  -- and against a commit `gh` cannot be asked about at all --")
        eleventh = tmp / "eleventh"
        eleventh.mkdir()
        unasked = build(eleventh)
        with_claimer(unasked)
        signable(unasked)
        git(unasked, "add", "-A")
        git(unasked, "commit", "-qm", "the checkout carries the claimer")
        git(unasked, "checkout", "-q", "-b", "feature")
        write(unasked, "docs/DECISIONS.md", DECISIONS_MAIN + f"\n## {SD} — Third\n\nbody\n")
        git(unasked, "add", "-A")
        git(unasked, "commit", "-qm", "the branch writes a slug")
        broken = FakeGh(eleventh / "gh")
        broken.script("default", [None])
        with broken:
            out, code = drive_claim_commit(waitable(deadline=0.5), unasked, "feature")
        ok(code != 0 and "could not be read" in out,
           "a `gh` that cannot answer refuses the merge and SAYS SO IN THOSE WORDS — an "
           "outage read as an empty roster would be the same defect one function along, "
           "and the message is the only place the two are distinguishable to a reader", out)

        # ------------------------------------------ what a commit CARRIES, once it has landed
        #
        # THE INVARIANT IS `MAIN CARRIES NO SLUG` AND EVERY READER ABOVE ASKS ABOUT A CHECKOUT.
        # It failed twice in silence: `make merge` runs the merge script of whatever checkout
        # invoked it, and a checkout older than the claim has no claim in it to run. So the
        # reading that matters afterwards is of the COMMIT, and these arms are mostly about
        # keeping it from quietly becoming a reading of the working tree again.
        print("\n  -- what a commit carries, read from the commit --")
        twelfth = tmp / "landed"
        twelfth.mkdir()
        landed = build(twelfth)
        with_claimer(landed)
        git(landed, "add", "-A")
        git(landed, "commit", "-qm", "the checkout carries the claimer")
        clean_rev = git(landed, "rev-parse", "HEAD").strip()
        git(landed, "checkout", "-q", "-b", "feature")
        write(landed, "docs/DECISIONS.md", DECISIONS_MAIN + f"\n## {SD} — Third\n\nbody\n")
        git(landed, "add", "-A")
        git(landed, "commit", "-qm", "a slug lands")
        slug_rev = git(landed, "rev-parse", "HEAD").strip()

        out, code = claim_rc(landed, "--landed", slug_rev)
        ok(code == 3 and SD in out,
           "a commit carrying a slug is reported, by name, and exits 3", out)

        out, code = claim_rc(landed, "--landed", clean_rev)
        ok(code == 0 and SD not in out,
           "a commit whose ids are all numbers reads clean", out)

        # THE ARM THAT KEEPS IT A COMMIT READER. The working tree here IS the slugged one —
        # HEAD is `feature` — so a reader that fell back to the checkout would report the slug
        # for a clean commit. That regression is invisible in every other arm.
        out, code = claim_rc(landed, "--landed", clean_rev)
        ok(code == 0,
           "AND THE WORKING TREE IS NOT THE SUBJECT: standing on the slugged branch, a clean "
           "commit still reads clean", out)

        git(landed, "checkout", "-q", clean_rev)
        out, code = claim_rc(landed, "--landed", slug_rev)
        ok(code == 3 and SD in out,
           "and the same the other way — standing on a clean tree, the slugged commit still "
           "reports", out)
        git(landed, "checkout", "-q", "feature")

        out, code = claim_rc(landed, "--landed", "no-such-rev")
        ok(code == 2 and code != 0,
           "a rev that names nothing REFUSES rather than reading clean — an answer it has "
           "not got is not a pass", out)

        # ------------------------------------------------- and the half of the merge that asks
        print("\n  -- the merge reports what main landed with --")
        out, code = drive_landed_half(landed, slug_rev)
        ok(code == 1 and SD in out,
           "landed_half reports a slug on the commit main moved to, and its status says so",
           out)
        ok("MERGE ITSELF COMPLETED" in out,
           "AND SAYS THE MERGE COMPLETED, because it did — a status read as a failed merge "
           "would send the next session to re-run one that already happened", out)

        out, code = drive_landed_half(landed, clean_rev)
        ok(code == 0, "and a clean commit passes it", out)

        # A CLAIMER THAT CANNOT ANSWER IS NOT A CLEAN ANSWER. This is the same rule the claim
        # commit's wait is built on, one function along, and it is the arm that stops the
        # `code == 0` test from being written as `code != 3`.
        write(landed, "scripts/claim-ids.py",
              "import sys\nsys.stderr.write('the claimer is not what you think\\n')\n"
              "sys.exit(2)\n")
        out, code = drive_landed_half(landed, clean_rev)
        ok(code == 1 and "could not be asked" in out,
           "a claimer that cannot answer is REPORTED, never read as a clean main", out)

        # ------------------------------------------------------------------------------
        # THE CORPUS AS A DIRECTORY, which is the shape the product actually has now.
        #
        # EVERY ARM ABOVE WRITES `docs/DECISIONS.md` AS ONE FILE, and they all still pass —
        # the claimer falls back to that path when a tree has no manifest, so a pre-split
        # repository keeps working. That fallback is also how this whole file could have gone
        # on being green against a layout the product no longer has, which is the failure
        # this repo makes mechanical rather than trusting. So the directory gets its own
        # fixture, and the two things a single file cannot express are asserted here: the
        # entry FILE is renamed, and the MANIFEST follows it.
        print("\n  -- the corpus as a directory --")
        split = tmp / "split"
        git(split.parent, "clone", "-q", str(tmp / "origin.git"), "split")
        git(split, "checkout", "-q", "-b", "directory")
        with_claimer(split)
        entry = f"D-{'a-third-thing'}"
        write(split, "docs/decisions/_preamble.md", "# Fixture\n")
        write(split, "docs/decisions/D001-first.md", f"## {D(1)} — First\n\nbody\n")
        write(split, "docs/decisions/D002-second.md", f"## {D(2)} — Second\n\nbody\n")
        write(split, f"docs/decisions/{entry}-a-third-thing.md",
              f"## {entry} — A third thing\n\nbody\n")
        # THE BRANCH DOES NOT REGISTER ITS OWN ENTRY, and that is the point rather than an
        # oversight. If it had to, every entry-adding branch would append to one shared JSON
        # array at the same position — the collision this whole split removes, wearing a
        # different file extension. Membership is derived until the claim settles it.
        write(split, "docs/decisions/ORDER.json", json.dumps({
            "source": "docs/DECISIONS.md",
            "order": ["_preamble.md", "D001-first.md", "D002-second.md"],
        }, indent=2) + "\n")
        write(split, "docs/DECISIONS.md", "# Stub\n\nThe entries are in `docs/decisions/`.\n")
        write(split, "CLAUDE.md",
              f"# Fixture\n\nthe branch cites {entry} twice: {entry}.\n\n"
              f"```\n{D(1):<4} First\n{D(2):<4} Second\n```\n")
        git(split, "add", "-A")
        git(split, "commit", "-qm", "a branch writes a slug into the directory")

        out = claim(split, "--root", str(split))
        # THE NUMBER IS READ OUT OF THE PREVIEW, NEVER ASSUMED. Which id this fixture's main
        # has reached depends on every arm above it, and an assertion that hardcoded one
        # would break the next time somebody adds an arm — testing the test's arithmetic
        # rather than the claimer's.
        allocated = re.search(re.escape(entry) + r"\s+->\s+(D[0-9]+)", out)
        ok(allocated is not None,
           "the slug is FOUND in the directory, and allocated against main's ceiling", out)
        number = int(allocated.group(1)[1:]) if allocated else 0

        claim(split, "--root", str(split), "--write")
        landed_name = f"D{number:03d}-a-third-thing.md"
        ok((split / "docs/decisions" / landed_name).exists(),
           "the entry FILE is renamed to its allocated number",
           str(sorted(x.name for x in (split / "docs/decisions").glob("*.md"))))
        ok(not (split / f"docs/decisions/{entry}-a-third-thing.md").exists(),
           "and the slug-named file is gone rather than left beside it")
        manifest = json.loads((split / "docs/decisions/ORDER.json").read_text(encoding="utf-8"))
        ok(landed_name in manifest["order"],
           "the claim APPENDS the unregistered entry to the manifest, under its new name",
           str(manifest["order"]))
        ok(manifest["order"][-1] == landed_name,
           "and appends it LAST, so the three non-entry sections keep their place",
           str(manifest["order"][-3:]))
        index_lines = [l for l in (split / "CLAUDE.md").read_text(encoding="utf-8").split("\n")
                       if re.match(r"^D[0-9]+\s", l)]
        ok(any(l.startswith(f"D{number} ") for l in index_lines),
           "and the CLAUDE.md index is regenerated with the allocated number",
           str(index_lines))
        ok(f"{entry}-a-third-thing.md" not in manifest["order"],
           "and does not still name the file that no longer exists")
        # THE INVARIANT, rather than one mechanism that could break it. The manifest and the
        # directory have to move together: a rename with no manifest update, or a manifest
        # update with no rename, leaves a name pointing at nothing and the corpus stops
        # reassembling with every audit row still green. An earlier version of this arm
        # asserted that a blind substitution had not mangled the name — which tests nothing,
        # because the claimer's token grammar already declines that match.
        ok(all((split / "docs/decisions" / name).exists() for name in manifest["order"]),
           "every name in the manifest is a file that exists — the two moved together",
           str([n for n in manifest["order"]
                if not (split / "docs/decisions" / n).exists()]))
        body = (split / "docs/decisions" / landed_name).read_text(encoding="utf-8")
        ok(body.startswith(f"## D{number} — A third thing"),
           "the HEADING inside it is the number, not the slug", body.split("\n")[0])
        ok(entry not in (split / "CLAUDE.md").read_text(encoding="utf-8"),
           "and every citation of the slug elsewhere was substituted too")

    print("\nclaim self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
