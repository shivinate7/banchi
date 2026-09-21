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
import uuid
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

# `gh pr view <n> --json ...` — what the WAIT asks to learn whether the branch can still
# merge. Answered MERGEABLE unless the fixture wrote `mergeable.txt`, because a fake that
# could not answer at all would leave every claim-half arm exercising the reader's
# unreadable path and nothing else.
if argv[:2] == ["pr", "view"]:
    book = os.path.join(home, "mergeable.txt")
    state = open(book).read().strip() if os.path.exists(book) else "MERGEABLE"
    print(json.dumps({"number": 1, "title": "t", "url": "u", "state": "OPEN",
                      "mergeable": state, "mergeStateStatus": "CLEAN",
                      "headRefName": "feature", "mergeCommit": None}))
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


def build_split(tmp: Path) -> Path:
    """Like `build`, but the decision corpus is a DIRECTORY with a manifest — the shape this
    repo actually has since D160, and the only shape `--unclaim` can act on for a decision id:
    it is the entry's own FILENAME that survives a claim once the heading is overwritten with
    a number (`find_decision_file`), and a flat `docs/DECISIONS.md` has no filename per entry
    to read that back from.
    """
    origin = tmp / "origin.git"
    work = tmp / "work"
    seed = tmp / "seed"
    seed.mkdir()
    git(seed, "init", "-q", ".")
    write(seed, "docs/decisions/_preamble.md", "# Fixture\n")
    write(seed, "docs/decisions/D001-first.md", f"## {D(1)} — First\n\nbody\n")
    write(seed, "docs/decisions/D002-second.md", f"## {D(2)} — Second\n\nbody\n")
    write(seed, "docs/decisions/ORDER.json", json.dumps({
        "source": "docs/DECISIONS.md",
        "order": ["_preamble.md", "D001-first.md", "D002-second.md"],
    }, indent=2) + "\n")
    write(seed, "docs/DECISIONS.md", "# Stub\n\nThe entries are in `docs/decisions/`.\n")
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


def snapshot(root: Path) -> dict:
    """Every tracked-looking file's bytes, keyed by relative path — for a byte-identical
    round-trip assertion that does not care which files moved, only whether the CONTENT did.

    `__pycache__` IS NOT TRACKED-LOOKING, and including it is what made this comparison flaky
    rather than wrong: CPython writes `scripts/__pycache__/*.pyc` the first time a helper module
    (`decisions_corpus`, `index-decisions`) is imported by a subprocess this test spawns, so a
    "before" snapshot taken ahead of the first claim and an "after" snapshot taken past several
    more subprocess calls can disagree on cache files that were never part of the tree either
    snapshot is actually asking about. Measured: passed locally where an earlier run had already
    warmed the cache, failed on a clean CI checkout where it had not — the same tree, two
    different verdicts, which is the definition of a check that is not asking a real question.
    """
    out = {}
    for path in root.rglob("*"):
        if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts:
            out[str(path.relative_to(root))] = path.read_bytes()
    return out


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

        # ------------------------------- wait on required checks only (owner's word, 2026-09-19)
        # Four arms, matching D148's own four-part rule applied to the NARROWER roster:
        # (a) required green + non-required in progress -> merges; (b) required green +
        # non-required RED -> still refuses, because narrowing what is WAITED FOR is not
        # narrowing what is WATCHED FOR; (c) the protection endpoint unreadable -> falls back
        # to waiting for everything, as before; (d) an empty roster of required contexts is
        # never a pass on its own — it is treated the same as unreadable, never as "nothing
        # is required".
        print("\n  -- required green, non-required still running: this is the merge --")
        eyes = Scripted(reading(module, done("check"), done("revert-guard"),
                                running("design-check (1)")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks, "abc1234", 99, 0, eyes, watch.sleep,
                               watch.now, ("check", "revert-guard"))
        joined = "\n".join(lines)
        ok(green, "required checks complete and green is enough — a non-required run in "
           "progress does not hold the merge", joined)
        ok("design-check (1)" in joined and "not required" in joined,
           "and the still-running non-required run is NAMED at the moment of merging, not "
           "swallowed", joined)
        ok("browser matrix is not required and was not waited for" in joined,
           "and the fixed sentence is printed — a red there lands on main's own run and is "
           "fixed forward", joined)

        print("\n  -- required green, non-required RED: still refuses --")
        eyes = Scripted(reading(module, done("check"), done("revert-guard"),
                                done("design-check (1)", "failure")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks, "abc1234", 99, 0, eyes, watch.sleep,
                               watch.now, ("check", "revert-guard"))
        ok(not green and "did not pass" in "\n".join(lines),
           "A RED RUN THAT IS ALREADY VISIBLE REFUSES REGARDLESS OF WHETHER IT IS REQUIRED — "
           "a narrower wait is not a blindfold, and a known red is not something to merge "
           "past", "\n".join(lines))

        print("\n  -- a required check not yet attached holds the wait, same as absence --")
        eyes = Scripted(reading(module, done("check")),
                        reading(module, done("check"), done("revert-guard")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks, "abc1234", 99, 0, eyes, watch.sleep,
                               watch.now, ("check", "revert-guard"))
        ok(green and len(eyes.asked) == 3,
           "`revert-guard` had not attached yet on the first read — waited for, not treated "
           "as satisfied by its absence", "\n".join(lines) + "\nasked " + str(len(eyes.asked)))

        print("\n  -- a required check that never attaches never goes green --")
        eyes = Scripted(reading(module, done("check")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks, "abc1234", 99, 0, eyes, watch.sleep,
                               watch.now, ("check", "revert-guard"))
        ok(not green and "revert-guard" in "\n".join(lines) and "gave up" in "\n".join(lines),
           "`revert-guard` is REQUIRED and is never in the roster — the wait names it and "
           "runs out, rather than settling on `check` alone because nothing else is pending",
           "\n".join(lines))

        print("\n  -- the floor is the parent's REQUIRED count, not its total --")
        # Both required names are attached (`missing` is empty), so this is a floor case and
        # not a missing-name one: floor 3 against a roster that only ever carries the two
        # required contexts never fills, however many of the roster's OTHER runs attach.
        eyes = Scripted(reading(module, done("check"), done("revert-guard"), done("also-here")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks, "abc1234", 99, 3, eyes, watch.sleep,
                               watch.now, ("check", "revert-guard"))
        ok(not green and "parent commit carried 3" in "\n".join(lines),
           "the floor counts required contexts only — three non-required runs beside the two "
           "required ones does not fill a floor of 3 required", "\n".join(lines))

        print("\n  -- required_contexts: an unreadable protection endpoint fails CLOSED --")
        module2 = waitable()
        def unreadable_gh():
            return module2.Ran(False, "", "gh: HTTP 404")
        ok(module2.required_contexts(unreadable_gh) is None,
           "an unreadable answer returns None, and None is the caller's OWN fallback: wait "
           "for every check run, exactly as before 2026-09-19")

        print("\n  -- required_contexts: an EMPTY roster is never a pass --")
        def empty_gh():
            return module2.Ran(True, json.dumps({"contexts": []}), "")
        ok(module2.required_contexts(empty_gh) is None,
           "an empty `contexts` list cannot be told apart from `everything is required`, so "
           "it is treated the same as unreadable rather than as `nothing is required`")
        def junk_gh():
            return module2.Ran(True, json.dumps({"contexts": [123, None]}), "")
        ok(module2.required_contexts(junk_gh) is None,
           "a `contexts` list with nothing readable as a name resolves to empty, and empty "
           "is unreadable's twin here too — not silently `()`, which a caller could mistake "
           "for `nothing is required`")

        print("\n  -- required_contexts: a real roster is read and returned --")
        def real_gh():
            return module2.Ran(True, json.dumps({"contexts": ["check", "revert-guard"]}), "")
        ok(module2.required_contexts(real_gh) == ("check", "revert-guard"),
           "a well-formed answer is returned as the tuple the wait narrows on")

        print("\n  -- attached_count, narrowed to the required names --")
        eyes = Scripted(reading(module, done("check"), done("revert-guard"), done("browser-scope")))
        ok(module.attached_count("parent-sha", eyes, required=("check", "revert-guard")) == 2,
           "counts only the required-named runs the parent carries, not its total of three")
        ok(module.attached_count("parent-sha", eyes, required=None) == 3,
           "and with no required set, it is the old, unnarrowed count")

        print("\n  -- a roster that grows between two complete reads is not settled --")
        eyes = Scripted(reading(module, done("check")),
                        reading(module, done("check"), done("revert-guard")))
        watch = Clock()
        green, lines = quietly(module.wait_for_checks,"abc1234", 99, 0, eyes, watch.sleep, watch.now)
        ok(green and len(eyes.asked) == 3,
           "the first complete reading was not concluded from, because the next one was "
           "bigger — the settle is what catches a workflow GitHub dispatches late",
           str(len(eyes.asked)))

        # ------------------- and whether it can still merge, watched WHILE it waits
        # OBSERVED ON PR #436, 2026-09-20. The wait watched check runs and nothing else, so a
        # branch that went DIRTY under it — another session merged first — kept it sitting
        # while `gh pr view 436` said OPEN / DIRTY. The claim commit's checks are unaffected
        # by somebody else's merge, so they go on passing and the 45-minute deadline is the
        # only thing that ends it.
        #
        # THE `UNKNOWN` ARM IS THE ONE THAT MATTERS MOST and it is mutation-proved below:
        # GitHub answers `UNKNOWN` routinely while it computes, so reading that as a conflict
        # would abort every merge this repo makes. Only the word `CONFLICTING` ends the wait.

        class Answers:
            """A mergeability reader answering from a list, holding the last, counting."""

            def __init__(self, *states) -> None:
                self.states = list(states)
                self.asked = 0

            def __call__(self) -> str:
                self.asked += 1
                return self.states[min(self.asked - 1, len(self.states) - 1)]

        print("\n  -- a branch that goes CONFLICTING under the wait ends it at once --")
        eyes = Scripted(reading(module, done("check"), running("design-check (1)")))
        watch = Clock()
        mergeable = Answers("MERGEABLE", "CONFLICTING")
        green, lines = quietly(module.wait_for_checks, "abc1234", 436, 0, eyes, watch.sleep,
                               watch.now, None, mergeable)
        joined = "\n".join(lines)
        ok(not green and "CONFLICTING" in joined,
           "PR #436's shape: the checks are still running and green, and the wait ends "
           "anyway because the merge can no longer happen", joined)
        ok("Main moved underneath the branch" in joined and "origin/main" in joined,
           "and it says WHY and what to do — main moved, bring it in and resolve — rather "
           "than reporting a timeout for a merge that was never going to succeed", joined)
        ok(watch.now() < module.CHECK_DEADLINE_SECONDS,
           "and it ends EARLY: the whole defect was spending the full deadline on this",
           str(watch.now()))

        print("\n  -- `UNKNOWN` is never read as conflicted --")
        # A roster that never completes, so the ONLY thing that could end this wait before
        # the deadline is the mergeability arm. It answers UNKNOWN forever.
        eyes = Scripted(reading(module, running("check")))
        watch = Clock()
        mergeable = Answers("UNKNOWN")
        green, lines = quietly(module.wait_for_checks, "abc1234", 99, 0, eyes, watch.sleep,
                               watch.now, None, mergeable)
        joined = "\n".join(lines)
        ok(not green and "gave up" in joined and "CONFLICTING" not in joined,
           "GitHub computes mergeability asynchronously and says `UNKNOWN` while it does. "
           "Reading that as a conflict would abort EVERY merge, so the wait runs to its own "
           "deadline on the checks instead — the mergeability arm says nothing", joined)
        ok(mergeable.asked > 1,
           "and it really was asked, repeatedly — an arm that is never reached would pass "
           "this for the wrong reason", str(mergeable.asked))

        print("\n  -- an unreadable answer, and a reader that throws, are both no news --")
        # A ROSTER THAT NEVER COMPLETES, for the same reason the `UNKNOWN` arm uses one: a
        # wait whose checks go green in two reads has spent two seconds of the fake clock and
        # has NOT ASKED about mergeability at all, so it would pass this whatever the reader
        # answered. That is the shape `a-guard-must-see-its-subject` names, and it survived a
        # mutation here before this comment existed.
        class Throwing:
            def __init__(self) -> None:
                self.asked = 0

            def __call__(self) -> str:
                self.asked += 1
                raise RuntimeError("the network went away")

        for label, answers in (("an empty answer", Answers("")),
                               ("a word this guard does not know", Answers("BLOCKED")),
                               ("a reader that RAISES", Throwing())):
            eyes = Scripted(reading(module, running("check")))
            watch = Clock()
            green, lines = quietly(module.wait_for_checks, "abc1234", 99, 0, eyes,
                                   watch.sleep, watch.now, None, answers)
            joined = "\n".join(lines)
            ok(not green and "gave up" in joined and "CONFLICTING" not in joined,
               "{0} does not end the wait — absence is not evidence here either, and the "
               "checks are what decide".format(label), joined)
            ok(answers.asked > 1,
               "and it was really asked — a wait whose checks go green in two reads never "
               "reaches this arm at all, and would pass it for the wrong reason",
               str(answers.asked))

        print("\n  -- it is asked no oftener than the check poll, and far less --")
        # THE SHIPPED CONSTANTS, not this fixture's: `waitable()` sets the poll to 0 so the
        # fake clock can spend a deadline in a blink, and comparing against that would be an
        # assertion about the fixture.
        shipped = merge_pr_module()
        ok(shipped.MERGEABILITY_RECHECK_SECONDS >= shipped.CHECK_POLL_SECONDS,
           "the recheck interval is never shorter than the check poll — every reading is a "
           "`gh pr view` against somebody's rate limit",
           "{0} vs {1}".format(shipped.MERGEABILITY_RECHECK_SECONDS,
                               shipped.CHECK_POLL_SECONDS))
        eyes = Scripted(reading(module, running("check")))
        watch = Clock()
        counted = Answers("MERGEABLE")
        quietly(module.wait_for_checks, "abc1234", 99, 0, eyes, watch.sleep, watch.now,
                None, counted)
        rounds = len(eyes.asked)
        ok(counted.asked < rounds,
           "over one whole deadline it was asked fewer times than the checks were — the "
           "interval is real and not a poll-per-round",
           "{0} mergeability reads against {1} check reads".format(counted.asked, rounds))

        print("\n  -- and with no reader at all, nothing is asked --")
        eyes = Scripted(reading(module, done("check"), done("revert-guard")))
        watch = Clock()
        green, _ = quietly(module.wait_for_checks, "abc1234", 99, 0, eyes, watch.sleep,
                           watch.now)
        ok(green, "`mergeability=None` is the old behaviour exactly — the arithmetic above "
                  "is untouched by this")

        print("\n  -- the reader itself: what it makes of each answer gh can give --")
        ok(module.mergeability_reader(99, lambda n: ({"mergeable": "CONFLICTING"}, ""))()
           == "CONFLICTING", "a conflicting pull request reads as CONFLICTING")
        ok(module.mergeability_reader(99, lambda n: ({"mergeable": "MERGEABLE"}, ""))()
           == "MERGEABLE", "a mergeable one reads as MERGEABLE")
        ok(module.mergeability_reader(99, lambda n: ({"mergeable": None}, ""))() == "UNKNOWN",
           "a null `mergeable` is UNKNOWN — gh's own answer while GitHub computes it, and "
           "NEVER a conflict")
        ok(module.mergeability_reader(99, lambda n: (None, "gh: HTTP 502"))() == "",
           "a read that FAILED is empty, which is no news and never a conflict")

        def boom(number):
            raise RuntimeError("gh is not on PATH")

        ok(module.mergeability_reader(99, boom)() == "",
           "and a reader that raises answers empty rather than propagating — the wait must "
           "not die of a network blip")

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
        # D249: THE REAL 2026-09-20 ESCAPE.
        #
        # A branch adding a decision entry touches only its own FILE, by design — the
        # manifest is settled at claim time, never before (`corpus_order`'s own docstring).
        # `--landed`/`landed_half` ask a REF what it carries, and `corpus_text_at` used to
        # trust that REF's own `ORDER.json` alone, with no `git ls-tree` fallback for the
        # file the manifest had never heard of. A correctly-slugged, unclaimed entry reached
        # `origin/main` this way and both readers reported it clean.
        print("\n  -- the real escape: an unregistered entry FILE, read from a REF --")
        esc = tmp / "escape"
        esc.mkdir()
        escaped = build_split(esc)
        with_claimer(escaped)
        git(escaped, "add", "-A")
        git(escaped, "commit", "-qm", "the checkout carries the claimer")
        git(escaped, "push", "-q", "origin", "main")
        git(escaped, "checkout", "-q", "-b", "feature")
        esc_entry = "D-" + "a-real-escape"
        write(escaped, f"docs/decisions/{esc_entry}.md",
              f"## {esc_entry} — A real escape\n\nbody\n")
        git(escaped, "add", "-A")
        git(escaped, "commit", "-qm", "a branch adds an entry, and never touches ORDER.json")
        escape_rev = git(escaped, "rev-parse", "HEAD").strip()
        # fast-forward main onto it WITH NO CLAIM EVER RUN — the scenario `--landed` exists
        # to catch after the fact.
        git(escaped, "checkout", "-q", "main")
        git(escaped, "merge", "-q", "--ff-only", "feature")

        before_fix = claim_rc(escaped, "--landed", escape_rev)
        ok(before_fix[1] == 3 and esc_entry in before_fix[0],
           "THE DEFECT, REPRODUCED: an unregistered decision FILE reaches `origin/main` "
           "and `--landed` — the merge's own backstop — must not read it as clean, because "
           "ORDER.json alone does not name it", before_fix[0])

        out, code = drive_landed_half(escaped, escape_rev)
        ok(code == 1 and esc_entry in out,
           "and `make merge`'s own `landed_half`, what a real merge actually calls, catches "
           "the same escape", out)

        # ---- recognition is by the COMPLEMENT, not by SLUG's own shape ----
        #
        # Each arm below is its own commit on its own branch, one malformed heading at a
        # time, checked with `--landed` against a REF that already has the file (so the
        # `corpus_order_at` fix above is not what is under test here — the manifest DOES
        # name these files).
        def landed_repo(tmp_dir: Path, heading: str) -> Tuple[Path, str]:
            tmp_dir.mkdir(parents=True, exist_ok=True)
            work = build_split(tmp_dir)
            with_claimer(work)
            entry_slug = "D-" + "a-shape-arm"
            write(work, f"docs/decisions/{entry_slug}.md", f"{heading}\n\nbody\n")
            write(work, "docs/decisions/ORDER.json", json.dumps({
                "source": "docs/DECISIONS.md",
                "order": ["_preamble.md", "D001-first.md", "D002-second.md",
                          f"{entry_slug}.md"],
            }, indent=2) + "\n")
            git(work, "add", "-A")
            git(work, "commit", "-qm", "a malformed heading, already in the manifest")
            rev = git(work, "rev-parse", "HEAD").strip()
            return work, rev

        print("\n  -- a mixed-case slug heading is unclaimed, not invisible --")
        upper = "## D-" + "A-shape-arm"
        work, rev = landed_repo(tmp / "upper", upper)
        out, code = claim_rc(work, "--landed", rev)
        ok(code == 3 and "-A-shape-arm" in out,
           "`DECISION_HEADING`'s SLUG alternative is lowercase-only and would have rejected "
           "this heading outright — the complement flags it unclaimed instead of walking "
           "past it silently", out)

        print("\n  -- a doubled-hyphen slug heading is unclaimed, not invisible --")
        doubled = "## D-" + "a--shape-arm"
        work, rev = landed_repo(tmp / "doubled", doubled)
        out, code = claim_rc(work, "--landed", rev)
        ok(code == 3 and "a--shape-arm" in out,
           "a doubled hyphen is not the SLUG grammar either, and the complement still "
           "refuses rather than reading the commit clean", out)

        print("\n  -- a leading-zero heading matches neither alternative, and is unclaimed --")
        zeroed = "## D0227"
        work, rev = landed_repo(tmp / "zeroed", zeroed)
        out, code = claim_rc(work, "--landed", rev)
        ok(code == 3 and "D0227" in out,
           "`D0227` fits neither the NUMBER alternative (a leading zero) nor the SLUG one "
           "(no hyphen) — the old code walked past it as neither claimed nor pending, and "
           "the complement now names it", out)

        print("\n  -- a `## Deferred`-shaped heading is NOT falsely reported --")
        deferred = "## Deferred — argued, not gated"
        work, rev = landed_repo(tmp / "deferred", deferred)
        out, code = claim_rc(work, "--landed", rev)
        ok(code == 0,
           "the character after `D` is `e`, neither a digit nor a hyphen — a subsection-"
           "shaped heading that merely starts with the letter is not mistaken for an "
           "unclaimed id", out)

        print("\n  -- positive control: an ordinary numbered heading stays clean --")
        numbered = f"## {D(3)} — An ordinary numbered entry"
        work, rev = landed_repo(tmp / "numbered", numbered)
        out, code = claim_rc(work, "--landed", rev)
        ok(code == 0, "a clean numbered heading is not swept up by the broader match", out)

        print("\n  -- positive control: an ordinary properly-slugged heading is still caught --")
        proper = "## D-" + "a-shape-arm"
        work, rev = landed_repo(tmp / "proper", proper)
        out, code = claim_rc(work, "--landed", rev)
        ok(code == 3 and "a-shape-arm" in out,
           "a heading the OLD code already recognised is still recognised", out)

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
        # THE 2026-09-19 SHAPE: A CITATION BY PATH TO THE SLUG'S OWN FILE. True the day it
        # was written — the unclaimed file really is named `{entry}-a-third-thing.md` — and
        # exactly what a blind token substitution turns into a path that has never existed,
        # because the claim also adds the number to the FILENAME in the same pass. This is
        # `docs/specs/revenue-plan.md`'s own line, reproduced rather than invented.
        write(split, "docs/specs/example.md",
              f"`docs/decisions/{entry}-a-third-thing.md` argues the key in full.\n")
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
        index_lines = [row for row in
                       (split / "CLAUDE.md").read_text(encoding="utf-8").split("\n")
                       if re.match(r"^D[0-9]+\s", row)]
        ok(any(row.startswith(f"D{number} ") for row in index_lines),
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

        # THE 2026-09-19 DEFECT: A PATH CITATION OF THE SLUG'S OWN FILE. `apply_to_text`
        # alone turns `` `docs/decisions/D-<slug>.md` `` into `` `docs/decisions/D<n>.md` ``
        # — a path that never existed, since the real file lands at `D<n>-<slug>.md` in the
        # SAME claim. Cite by id, never by path.
        example = (split / "docs/specs/example.md").read_text(encoding="utf-8")
        ok(f"docs/decisions/D{number}.md" not in example,
           "the claim does not leave behind a path to a file that was never created",
           example)
        ok("docs/decisions/" not in example,
           "no path survives the claim at all — the citation is dropped, not repaired",
           example)
        ok(example.strip() == f"D{number} argues the key in full.",
           "the path citation becomes a bare id citation, the form this repo already uses "
           "everywhere else",
           example)

        # --------------------------------------------------------------------------------
        # `--unclaim`: THE EXACT INVERSE, WHICH `stale_claims` NAMED AND NOTHING PERFORMED.
        #
        # Its own refusal text says "put the id back to the slug form and let the merge
        # allocate it again" — and until this, that sentence had no command behind it: a
        # human had to hand-rename the file, hand-edit the heading, and hand-find every
        # citation, which is exactly the error surface D140 exists to delete from the FORWARD
        # direction. It bit for real on 2026-09-12: a coordinating session hit this refusal
        # mid conflict-resolution and, with nothing to reach for, hand-picked new numbers
        # instead — one guess collided too, before landing on D188 — reproduced below as the
        # third arm.
        print("\n  -- --unclaim: the round trip is byte-identical --")
        rt = tmp / "roundtrip"
        rt.mkdir()
        trip = build_split(rt)
        with_claimer(trip)
        git(trip, "add", "-A")
        git(trip, "commit", "-qm", "the checkout carries the claimer")
        git(trip, "checkout", "-q", "-b", "feature")
        rt_entry = "D-" + "round-trip-thing"
        write(trip, f"docs/decisions/{rt_entry}.md",
              f"## {rt_entry} — A round trip thing\n\nbody\n")
        write(trip, "docs/CODES-DECISIONS.md", CODES_MAIN + f"\n## {SC} — Another\n\nbody\n")
        write(trip, "docs/GATES.md", GATES_MAIN + f"0. `step {SS}` **Third step** — done.\n")
        write(trip, "docs/map.py",
              MAP_MAIN.replace("]\n", '    {"n": "' + SS + '", "title": "Third"},\n]\n'))
        write(trip, "CLAUDE.md",
              f"# Fixture\n\nmain cites {D(2)} and step 2 and {C(1)}.\n"
              f"the branch cites {rt_entry}, {SC} and step {SS}.\n")
        git(trip, "add", "-A")
        git(trip, "commit", "-qm", "the branch writes a decision, a code and a step slug")

        before = snapshot(trip)
        claim(trip, "--root", str(trip), "--write")
        after_claim = snapshot(trip)
        ok(before != after_claim, "the forward claim actually changed the tree", "")

        # Read the allocated numbers back off the rewritten tree rather than re-deriving them,
        # so this arm does not silently start testing its own arithmetic.
        decision_file = next((trip / "docs/decisions").glob("D*-round-trip-thing.md"))
        d_number = decision_file.stem.split("-", 1)[0]              # zero-padded, e.g. D003
        d_number_bare = "D" + str(int(d_number[1:]))                # unpadded, as cited
        # NAMED BY ITS OWN TITLE, not "the first heading" — `docs/CODES-DECISIONS.md` already
        # carries C1 from the fixture seed, and a bare `(C\d+)` match would silently grab that
        # instead of the entry this arm just claimed.
        codes_match = re.search(r"^##\s+(C\d+)\s+—\s+Another$",
                                 (trip / "docs/CODES-DECISIONS.md").read_text(), re.M)
        step_match = re.search(r"^(\d+)\.\s+\*\*Third step\*\*", (trip / "docs/GATES.md").read_text(),
                                re.M)
        c_number = codes_match.group(1) if codes_match else None
        s_number = step_match.group(1) if step_match else None
        ok(c_number is not None and s_number is not None,
           "the codes and step ids landed and are readable back off the tree",
           f"c={c_number} s={s_number}")

        _, rc = claim_rc(trip, "--unclaim", d_number_bare, "--ref", "origin/main", "--write")
        ok(rc == 0, "unclaiming the decision succeeds")
        _, rc = claim_rc(trip, "--unclaim", "C" + c_number[1:], "--to-slug", "second-code",
                         "--ref", "origin/main", "--write")
        ok(rc == 0, "unclaiming the codes id succeeds, given --to-slug")
        _, rc = claim_rc(trip, "--unclaim", f"step {s_number}", "--to-slug", SS,
                         "--ref", "origin/main", "--write")
        ok(rc == 0, "unclaiming the step succeeds, given --to-slug")

        after_unclaim = snapshot(trip)
        ok(after_unclaim == before,
           "THE TREE IS BYTE-IDENTICAL TO BEFORE THE CLAIM — file renamed back, heading "
           "restored, every citation restored, ORDER.json no longer lists it as a numbered "
           "entry",
           "\n".join(sorted(set(before) ^ set(after_unclaim))) or
           "\n".join(f"{k}:\nBEFORE={before.get(k)!r}\nAFTER={after_unclaim.get(k)!r}"
                     for k in before if before.get(k) != after_unclaim.get(k)))

        again = claim(trip, "--root", str(trip), "--porcelain")
        ok(f"{rt_entry}\t{d_number_bare}" in again,
           "and a fresh plan re-offers the SAME number, since nothing on main has moved",
           again)

        print("\n  -- --unclaim: refuses when `ref`'s copy IS this entry --")
        # `claim a slug, simulate it landing on origin/main ... then attempt --unclaim on that
        # SAME number from a DIFFERENT branch that also happens to reference it — must REFUSE`.
        land = tmp / "landed_same"
        land.mkdir()
        landed_work = build_split(land)
        with_claimer(landed_work)
        git(landed_work, "add", "-A")
        git(landed_work, "commit", "-qm", "the checkout carries the claimer")
        git(landed_work, "push", "-q", "origin", "main")
        git(landed_work, "checkout", "-q", "-b", "lander")
        landed_entry = "D-" + "landed-thing"
        write(landed_work, f"docs/decisions/{landed_entry}.md",
              f"## {landed_entry} — A landed thing\n\nbody\n")
        git(landed_work, "add", "-A")
        git(landed_work, "commit", "-qm", "a branch writes the entry")
        claim(landed_work, "--root", str(landed_work), "--write")
        git(landed_work, "add", "-A")
        git(landed_work, "commit", "-qm", "claim it")
        git(landed_work, "push", "-q", "origin", "lander")
        # fast-forward main onto it, exactly as `make merge`'s local half would
        git(landed_work, "checkout", "-q", "main")
        git(landed_work, "merge", "-q", "--ff-only", "lander")
        git(landed_work, "push", "-q", "origin", "main")
        landed_number = next((landed_work / "docs/decisions").glob("D*-landed-thing.md")).stem.split("-", 1)[0]
        landed_bare = "D" + str(int(landed_number[1:]))

        # a DIFFERENT branch, cut from main AFTER the merge, so its own copy of this entry is
        # byte-identical to main's — this is the tree a person confused about which number to
        # unclaim would actually be standing in.
        other_branch = tmp / "other_branch"
        subprocess.run(["git", "clone", "-q", str(land / "origin.git"), str(other_branch)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        git(other_branch, "checkout", "-q", "-b", "confused")

        before_refuse = snapshot(other_branch)
        out, rc = claim_rc(other_branch, "--unclaim", landed_bare, "--ref", "origin/main")
        ok(rc == 3 and "REFUSED" in out and "IS this entry" in out,
           "REFUSES rather than reverting an id `ref` genuinely already carries as this "
           "entry — unclaiming it would corrupt the citation main's own copy depends on",
           out)
        out, rc = claim_rc(other_branch, "--unclaim", landed_bare, "--ref", "origin/main",
                           "--write")
        ok(rc == 3, "and `--write` refuses too, not only the preview", out)
        ok(snapshot(other_branch) == before_refuse,
           "and NOTHING WAS TOUCHED — a refusal that half-writes would leave the tree worse "
           "than the collision it was asked to fix")

        print("\n  -- --unclaim: the actual 2026-09-12 shape D186 landed over, end to end --")
        # Two branches, cut from the SAME commit, each honestly claiming its OWN unrelated
        # slug as the next free number — and losing a race for that number to each other,
        # the shape D186's own merge collided with. The remedy is --unclaim on the branch
        # that merges second, followed by an ordinary re-plan: zero hand-editing.
        inc = tmp / "incident"
        inc.mkdir()
        inc_a = tmp / "incident_a"
        inc_b = tmp / "incident_b"
        base_inc = build_split(inc)
        with_claimer(base_inc)
        git(base_inc, "add", "-A")
        git(base_inc, "commit", "-qm", "the checkout carries the claimer")
        git(base_inc, "push", "-q", "origin", "main")
        subprocess.run(["git", "clone", "-q", str(inc / "origin.git"), str(inc_a)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        subprocess.run(["git", "clone", "-q", str(inc / "origin.git"), str(inc_b)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

        slug_a = "D-" + "first-racer"
        slug_b = "D-" + "second-racer"

        git(inc_a, "checkout", "-q", "-b", "branch-a")
        write(inc_a, f"docs/decisions/{slug_a}.md", f"## {slug_a} — First racer\n\nbody\n")
        git(inc_a, "add", "-A")
        git(inc_a, "commit", "-qm", "branch A writes its own slug")
        claim(inc_a, "--root", str(inc_a), "--write")
        git(inc_a, "add", "-A")
        git(inc_a, "commit", "-qm", "branch A claims it")
        git(inc_a, "push", "-q", "origin", "branch-a")
        git(base_inc, "fetch", "-q", "origin", "branch-a")
        git(base_inc, "merge", "-q", "--ff-only", "origin/branch-a")
        git(base_inc, "push", "-q", "origin", "main")

        # branch B was cut BEFORE branch A merged, so its own claim is honest at the time —
        # both branches allocate the SAME next-free number for two UNRELATED entries.
        git(inc_b, "checkout", "-q", "-b", "branch-b")
        write(inc_b, f"docs/decisions/{slug_b}.md", f"## {slug_b} — Second racer\n\nbody\n")
        git(inc_b, "add", "-A")
        git(inc_b, "commit", "-qm", "branch B writes its own, unrelated slug")
        claim(inc_b, "--root", str(inc_b), "--write")
        git(inc_b, "add", "-A")
        git(inc_b, "commit", "-qm", "branch B claims it, honestly, before seeing A merge")

        git(inc_b, "fetch", "-q", "origin", "main")
        out, rc = claim_rc(inc_b, "--stale")
        b_number_path = next((inc_b / "docs/decisions").glob("D*-second-racer.md"))
        b_bare = "D" + str(int(b_number_path.stem.split("-", 1)[0][1:]))
        ok(rc == 3 and "REFUSED" in out and b_bare in out,
           "`--stale` catches the real collision — TWO UNRELATED entries independently "
           "claimed the same number, the shape D186's own merge landed over, and this is "
           "the CHEAP early warning `stale_claim()` reads before a merge is even attempted",
           out)

        before_incident = snapshot(inc_b)
        _, rc = claim_rc(inc_b, "--unclaim", b_bare, "--ref", "origin/main")
        ok(rc == 0, "--unclaim on the branch that lost the race PREVIEWS cleanly")
        ok(snapshot(inc_b) == before_incident, "and the preview wrote nothing")
        out, rc = claim_rc(inc_b, "--unclaim", b_bare, "--ref", "origin/main", "--write")
        ok(rc == 0 and "DIFFERENT entry" in out,
           "and --write PERFORMS it, naming the collision as the reason it is safe rather "
           "than a reason to refuse", out)

        replanned = claim(inc_b, "--root", str(inc_b), "--porcelain")
        fresh_match = re.search(re.escape(slug_b) + r"\t(D[0-9]+)", replanned)
        ok(fresh_match is not None and fresh_match.group(1) != b_bare,
           "a normal re-plan allocates a FRESH number against main as it stands — zero "
           "hand-editing, which is the whole point", replanned)
        claim(inc_b, "--root", str(inc_b), "--write")
        out, rc = claim_rc(inc_b, "--stale")
        ok(rc == 0, "and the branch is clean again", out)

        print("\n  -- --unclaim: the citation substitution is the FORWARD grammar, reversed --")
        # Reuses `apply_to_text`'s own `(?<![-\w])...(?![-\w])` boundary rather than a second
        # implementation — proved the same way the forward direction's own boundary bug was
        # found: a shorter token that is a PREFIX of a longer, unrelated one.
        bnd = tmp / "boundary"
        bnd.mkdir()
        edge = build_split(bnd)
        with_claimer(edge)
        git(edge, "add", "-A")
        git(edge, "commit", "-qm", "the checkout carries the claimer")
        git(edge, "checkout", "-q", "-b", "feature")
        edge_entry = "D-" + "edge-thing"
        write(edge, f"docs/decisions/{edge_entry}.md",
              f"## {edge_entry} — An edge thing\n\nbody\n")
        look_alike_30 = "D" + "30"
        look_alike_300 = "D" + "300"
        write(edge, "CLAUDE.md",
              f"# Fixture\n\ncites {edge_entry} in prose, `{edge_entry}` in a code span, and "
              f"the unrelated {look_alike_30} and {look_alike_300}.\n\n"
              f"```\n{D(1):<4} First\n{D(2):<4} Second\n```\n")
        git(edge, "add", "-A")
        git(edge, "commit", "-qm", "a slug beside look-alike numbers, in prose and a code span")

        claim(edge, "--root", str(edge), "--write")
        claimed_claude = (edge / "CLAUDE.md").read_text(encoding="utf-8")
        edge_number_path = next((edge / "docs/decisions").glob("D*-edge-thing.md"))
        edge_bare = "D" + str(int(edge_number_path.stem.split("-", 1)[0][1:]))
        ok(look_alike_30 in claimed_claude and look_alike_300 in claimed_claude,
           "claiming the slug does not disturb an unrelated look-alike NUMBER beside it",
           claimed_claude)

        claim_rc(edge, "--unclaim", edge_bare, "--ref", "origin/main", "--write")
        unclaimed_claude = (edge / "CLAUDE.md").read_text(encoding="utf-8")
        ok(look_alike_30 in unclaimed_claude and look_alike_300 in unclaimed_claude,
           "AND UNCLAIMING IT DOES NOT EITHER — the exact `\\b`-boundary bug this repo was "
           "burned by once already, reused rather than re-derived on the way back",
           unclaimed_claude)
        ok(edge_entry in unclaimed_claude,
           "the slug is restored in BOTH the prose citation and the code span", unclaimed_claude)
        ok(f"`{edge_entry}`" in unclaimed_claude,
           "the code span's own backticks survive untouched around it", unclaimed_claude)
        ok(D(1) in unclaimed_claude and D(2) in unclaimed_claude,
           "and reverting one id never touches an UNRELATED already-numbered id's own "
           "citations", unclaimed_claude)

        print("\n  -- --unclaim: refuses cleanly on a bad ident or a step/codes id with no "
              "--to-slug --")
        bad = tmp / "bad_idents"
        bad.mkdir()
        badwork = build_split(bad)
        out, rc = claim_rc(badwork, "--unclaim", "D-" + "some-slug", "--ref", "origin/main")
        ok(rc == 2 and "REFUSED" in out and "never a slug" in out,
           "a SLUG is refused — there is nothing to unclaim from a slug", out)
        out, rc = claim_rc(badwork, "--unclaim", "D" + "999", "--ref", "origin/main")
        ok(rc == 2 and "REFUSED" in out,
           "a number nothing here claimed is refused rather than silently doing nothing", out)
        out, rc = claim_rc(badwork, "--unclaim", "C1", "--ref", "origin/main")
        ok(rc == 2 and "REFUSED" in out and "--to-slug" in out,
           "a codes id with no --to-slug is refused, naming the flag it needs — a codes "
           "entry keeps its slug NOWHERE once claimed, unlike a decision's own filename", out)
        out, rc = claim_rc(badwork, "--unclaim", "step 1", "--ref", "origin/main")
        ok(rc == 2 and "REFUSED" in out and "--to-slug" in out,
           "and so is a build step, for the same reason", out)

        # ------------------------------------------------------------------------------
        # A SLUG BOTH SIDES CLAIM, UNDER TWO NUMBERS — the incident this file's own
        # session hit on 2026-09-12. #329 claimed a stranded slug as D185; #330 — cut
        # earlier from the same unclaimed file and never merged forward — ran `make
        # merge` and claimed the IDENTICAL file as the very next number of its own accord, because
        # `plan()` only asks what number is free on `ref`, never whether `ref` has
        # already resolved this exact slug under a different one. `stale_claims` cannot
        # see it either: no number #330 added was ever taken on `ref` — the number it picked was free —
        # so the collision surfaced only as a GitHub rename/rename merge conflict, after
        # the claim commit had already been pushed.
        print("\n  -- a slug both sides still hold unclaimed, claimed under two numbers --")
        shared = tmp / "shared-origin.git"
        seed2 = tmp / "seed2"
        seed2.mkdir()
        git(seed2, "init", "-q", ".")
        write(seed2, "docs/decisions/_preamble.md", "# Fixture\n")
        write(seed2, "docs/decisions/D001-first.md", f"## {D(1)} — First\n\nbody\n")
        stranded = "D-" + "a-shared-stranded-slug"
        write(seed2, f"docs/decisions/{stranded}.md",
              f"## {stranded} — Something nobody has claimed yet\n\nbody\n")
        write(seed2, "docs/decisions/ORDER.json", json.dumps({
            "source": "docs/DECISIONS.md",
            "order": ["_preamble.md", "D001-first.md"],
        }, indent=2) + "\n")
        write(seed2, "docs/DECISIONS.md", "# Stub\n\nThe entries are in `docs/decisions/`.\n")
        write(seed2, "CLAUDE.md", f"# Fixture\n\n```\n{D(1):<4} First\n```\n")
        git(seed2, "add", "-A")
        git(seed2, "commit", "-qm", "a shared unclaimed slug, on main")
        git(seed2, "branch", "-M", "main")
        subprocess.run(["git", "clone", "-q", "--bare", str(seed2), str(shared)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

        first = tmp / "first-branch"
        second = tmp / "second-branch"
        subprocess.run(["git", "clone", "-q", str(shared), str(first)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        subprocess.run(["git", "clone", "-q", str(shared), str(second)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        with_claimer(first)
        with_claimer(second)
        git(first, "checkout", "-q", "-b", "claims-it-first")
        git(second, "checkout", "-q", "-b", "never-merges-forward")

        # `first` claims the stranded slug and pushes straight to `main` — standing in for
        # #329's repair PR landing.
        claim(first, "--root", str(first), "--write")
        landed = sorted(p.name for p in (first / "docs/decisions").glob("D[0-9]*-a-shared*.md"))
        ok(len(landed) == 1, "the first branch claims the slug", str(landed))
        git(first, "add", "-A")
        git(first, "commit", "-qm", "the branch claims its slug")
        git(first, "checkout", "-q", "main")
        git(first, "merge", "-q", "--no-edit", "claims-it-first")
        git(first, "push", "-q", "origin", "main")

        # `second` never fetches that push. It still carries the ORIGINAL unclaimed file,
        # exactly as #330 did, and asks what IT would claim against `origin/main` — which
        # now HAS a claimed twin of the identical slug under a different number.
        git(second, "fetch", "-q", "origin", "main")
        out, code = claim_rc(second, "--stale")
        ok(code == 3, "`--stale` refuses rather than reporting clean", f"exit={code}\n{out}")
        ok("REFUSED" in out and stranded in out,
           "the stray unclaimed slug is named, not silently allocated a fresh number", out)
        ok(landed[0].split("-")[0] in out,
           "and the number it was ALREADY claimed under on origin/main is named", out)

        before = sorted(p.name for p in (second / "docs/decisions").glob("*.md"))
        out, code = claim_rc(second, "--write")
        ok(code == 3 and "REFUSED" in out,
           "`--write` refuses the same way — the duplicate is caught before anything is "
           "renamed, not after", out)
        after = sorted(p.name for p in (second / "docs/decisions").glob("*.md"))
        ok(before == after,
           "and nothing was renamed — no second number was minted for the same content",
           f"before={before}\nafter={after}")

        # ---------------------------------------------------------------------------
        print("\n  -- the 2026-09-19 shape: the race is lost and main is ALREADY MERGED IN --")
        # TONIGHT'S EXACT STATE, AND THE ONE `--unclaim` COULD NOT READ. Branch B loses the
        # race exactly as the arm above, and then does the documented pre-merge thing: fetch
        # `origin/main` and MERGE IT. Two entry files now carry one number — B's own and the
        # one the merge brought — and until 2026-09-19 `find_decision_file` refused rather
        # than resolving which was which: `no single docs/decisions/D<n>-*.md file in this
        # tree`, from the command whose whole purpose is this state.
        race = tmp / "race"
        race.mkdir()
        race_a = tmp / "race_a"
        race_b = tmp / "race_b"
        base_race = build_split(race)
        with_claimer(base_race)
        git(base_race, "add", "-A")
        git(base_race, "commit", "-qm", "the checkout carries the claimer")
        git(base_race, "push", "-q", "origin", "main")
        for clone in (race_a, race_b):
            subprocess.run(["git", "clone", "-q", str(race / "origin.git"), str(clone)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

        won = "D-" + "race-winner"
        lost = "D-" + "race-loser"

        # A's entry lands on main, and main cites it in prose and indexes it in CLAUDE.md.
        git(race_a, "checkout", "-q", "-b", "winner")
        write(race_a, f"docs/decisions/{won}.md", f"## {won} — The winner\n\nbody\n")
        claude_a = race_a / "CLAUDE.md"
        claude_a.write_text(claude_a.read_text(encoding="utf-8")
                            + f"\nmain's own prose cites {won} here.\n", encoding="utf-8")
        git(race_a, "add", "-A")
        git(race_a, "commit", "-qm", "the winner writes its slug")
        claim(race_a, "--root", str(race_a), "--write")
        git(race_a, "add", "-A")
        git(race_a, "commit", "-qm", "the winner claims it")
        git(race_a, "push", "-q", "origin", "winner")
        git(base_race, "fetch", "-q", "origin", "winner")
        git(base_race, "merge", "-q", "--ff-only", "origin/winner")
        git(base_race, "push", "-q", "origin", "main")

        # B claims the same number honestly, then merges main in — the routine, in order.
        git(race_b, "checkout", "-q", "-b", "loser")
        write(race_b, f"docs/decisions/{lost}.md", f"## {lost} — The loser\n\nbody\n")
        claude_b = race_b / "CLAUDE.md"
        claude_b.write_text(claude_b.read_text(encoding="utf-8")
                            + f"\nthis branch's own prose cites {lost} here.\n",
                            encoding="utf-8")
        git(race_b, "add", "-A")
        git(race_b, "commit", "-qm", "the loser writes its slug")
        claim(race_b, "--root", str(race_b), "--write")
        git(race_b, "add", "-A")
        git(race_b, "commit", "-qm", "the loser claims it, honestly, before seeing A merge")
        loser_file = next((race_b / "docs/decisions").glob("D*-race-loser.md"))
        shared = "D" + str(int(loser_file.stem.split("-", 1)[0][1:]))
        git(race_b, "fetch", "-q", "origin", "main")
        git(race_b, "merge", "origin/main", "-m", "merge main into the branch")
        # The merge conflicts in the two files both sides append to — resolve it the way a
        # person does, KEEPING BOTH SIDES, which is what produces the two-file state.
        conflicted = claude_b.read_text(encoding="utf-8")
        claude_b.write_text(
            re.sub(r"<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", r"\1\2",
                   conflicted, flags=re.S), encoding="utf-8")
        manifest_path = race_b / "docs/decisions/ORDER.json"
        manifest = json.loads(re.sub(
            r"<<<<<<< HEAD\n(.*?)=======\n.*?>>>>>>> [^\n]*\n", r"\1",
            manifest_path.read_text(encoding="utf-8"), flags=re.S))
        order = [name for name in manifest["order"] if "race-" not in name]
        order += sorted(x.name for x in (race_b / "docs/decisions").glob("D*-race-*.md"))
        manifest_path.write_text(json.dumps({**manifest, "order": order}, indent=2) + "\n",
                                 encoding="utf-8")
        git(race_b, "add", "-A")
        git(race_b, "commit", "-qm", "merge main into the branch")

        both = sorted(x.name for x in (race_b / "docs/decisions").glob("D[0-9]*-race-*.md"))
        ok(len(both) == 2,
           "the merge leaves TWO entry files carrying one number — the state tonight's "
           "`--unclaim` refused to read", str(both))

        out, rc = claim_rc(race_b, "--stale")
        ok(rc == 3 and "declared twice" in out and shared in out,
           "`--stale` catches it anyway — the MERGE moved the base it measures from, so the "
           "added-versus-taken difference reads clean and the duplicate count is what does "
           "not", out)
        ok("--unclaim " + shared in out,
           "and it names the command that fixes it, spelled so it can be run", out)

        before_race = snapshot(race_b)
        out, rc = claim_rc(race_b, "--unclaim", shared, "--ref", "origin/main")
        ok(rc == 0 and "DIFFERENT entry" in out,
           "`--unclaim` RESOLVES which of the two files is this branch's, where it refused "
           "`no single D<n>-*.md file in this tree` before", out)
        ok(snapshot(race_b) == before_race, "and the preview wrote nothing")

        out, rc = claim_rc(race_b, "--unclaim", shared, "--ref", "origin/main", "--write")
        ok(rc == 0, "and --write performs it", out)

        ok((race_b / "docs/decisions" / (lost + ".md")).exists(),
           "this branch's own entry is back under its slug filename")
        winner_file = next((race_b / "docs/decisions").glob("D*-race-winner.md"), None)
        ok(winner_file is not None,
           "and main's entry keeps its number AND its filename",
           str(sorted(x.name for x in (race_b / "docs/decisions").glob("*.md"))))
        ok(winner_file is not None
           and winner_file.read_text(encoding="utf-8").startswith(f"## {shared} "),
           "main's own heading is untouched — the substitution is keyed on the TOKEN, so "
           "without a guard it rewrites the OTHER entry's heading into this branch's slug",
           winner_file.read_text(encoding="utf-8") if winner_file else "")

        claude_after = claude_b.read_text(encoding="utf-8")
        ok(f"main's own prose cites {shared} here." in claude_after,
           "main's own prose citation is untouched — a half-reversed claim is worse than an "
           "unreversed one, and this is the half that was wrong", claude_after)
        ok(f"this branch's own prose cites {lost} here." in claude_after,
           "and this branch's own citation IS reverted", claude_after)

        out, rc = claim_rc(race_b, "--stale")
        ok(rc == 0, "the branch is clean again", out)
        replanned = claim(race_b, "--root", str(race_b), "--porcelain")
        fresh = re.search(re.escape(lost) + r"\t(D[0-9]+)", replanned)
        ok(fresh is not None and fresh.group(1) != shared,
           "and a plain re-plan allocates a FRESH number against main as it stands — the "
           "loser retries with a free number, with nobody unpicking anything", replanned)

        # ---------------------------------------------------------------------------
        print("\n  -- the claim is not spent on a pull request that cannot merge --")
        # THE ORDER, WHICH IS THE 2026-09-19 DEFECT ITSELF. The claim committed and pushed
        # before anything asked whether the pull request could merge at all — and the answer
        # was in a reply `main()` had already read for the head branch. These arms drive
        # `main()` with every half around the two under test stubbed, so what they assert is
        # the ORDER rather than either half's own body.
        gate = tmp / "gate"
        gate.mkdir()
        gate_repo = build_split(gate)
        with_claimer(gate_repo)
        git(gate_repo, "add", "-A")
        git(gate_repo, "commit", "-qm", "the checkout carries the claimer")

        def drive_main(repo: Path, pr_json: dict, github: Tuple, claims: bool,
                       claim_code: int = 0):
            """`main()` over `repo`, with the halves around the gate replaced by recorders."""
            module = merge_pr_module()
            seen = {"claim": 0, "rollback": [], "reads": 0}

            def read(number):
                seen["reads"] += 1
                return dict(pr_json), ""

            def claim_half(root, number, branch, confirm):
                seen["claim"] += 1
                if claims:
                    # A DISTINCT BODY EVERY TIME, because an identical one commits nothing
                    # and HEAD does not move — which makes the rollback arm below pass for
                    # the wrong reason, by having nothing to roll back.
                    (Path(root) / "claimed.txt").write_text(
                        "a claim {0}".format(uuid.uuid4()), encoding="utf-8")
                    git(Path(root), "add", "-A")
                    git(Path(root), "commit", "-qm", "Claim the ids this branch left as slugs")
                return claim_code

            def rollback(root, number, sha, branch):
                seen["rollback"].append(sha)

            # THE PAUSE AND THE CLOCK ARE REAL IN THE SHIPPED PATH and there is nothing to learn
            # from waiting it out here — the arm asks whether it RE-READS, not how long it
            # waited between reads.
            module.MERGEABILITY_PAUSE = 0
            module.MERGEABILITY_DEADLINE = 0.05
            module.repo_root = lambda cwd=None: str(repo)
            module.surface_half = lambda root, ref="refs/remotes/origin/main": 0
            module.pr_state = read
            module.claim_half = claim_half
            module.github_half = lambda number, confirm: github
            module.rollback_claim = rollback
            module.primary_half = lambda root, confirm: 0
            module.delete_head_branch = lambda root, number, confirm: None
            module.local_half = lambda root, commit, confirm: 0
            module.landed_half = lambda root, commit: 0
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = module.main(["77", "--confirm"])
            return buf.getvalue(), code, seen

        conflicting = {"number": 77, "title": "t", "url": "u", "state": "OPEN",
                       "mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY",
                       "headRefName": "feature", "mergeCommit": None}
        out, code, seen = drive_main(gate_repo, conflicting, (None, 0), claims=True)
        ok(code != 0 and "conflicts with its base" in out,
           "a CONFLICTING pull request is refused", out)
        ok(seen["claim"] == 0,
           "AND THE CLAIM NEVER RAN — nothing was allocated, committed or pushed for a "
           "merge that could not have happened", out)
        ok("NOTHING HAS BEEN CLAIMED" in out,
           "and the refusal says so, because the whole cost of the old order was a person "
           "not knowing what had already been pushed", out)

        mergeable = dict(conflicting, mergeable="MERGEABLE", mergeStateStatus="CLEAN")
        head_before = git(gate_repo, "rev-parse", "HEAD").strip()
        out, code, seen = drive_main(gate_repo, mergeable, (None, 1), claims=True)
        ok(seen["claim"] == 1, "a MERGEABLE one reaches the claim", out)
        claimed_sha = git(gate_repo, "rev-parse", "HEAD").strip()
        ok(seen["rollback"] == [claimed_sha],
           "and when the GitHub half refuses AFTERWARDS — the race that opens during the "
           "claim's own CI wait, which no gate before the claim can see — the claim this "
           "run made is backed out by its own sha",
           f"{seen['rollback']} vs {claimed_sha}")
        ok(claimed_sha != head_before, "the arm really did move HEAD, so it is not vacuous")

        out, code, seen = drive_main(gate_repo, mergeable, (None, 1), claims=False)
        ok(seen["rollback"] == [],
           "a run that claimed NOTHING backs nothing out — the rollback is keyed on this "
           "run having moved the branch, never on the refusal alone", out)

        unknown = dict(mergeable, mergeable="UNKNOWN", mergeStateStatus="UNKNOWN")
        out, code, seen = drive_main(gate_repo, unknown, (None, 0), claims=False)
        ok(code != 0 and "still UNKNOWN" in out,
           "an UNKNOWN that never resolves REFUSES rather than proceeding — an unread "
           "state is not a mergeable one, and a claim is never spent on a guess", out)
        ok(seen["claim"] == 0 and "NOTHING HAS BEEN CLAIMED" in out,
           "and nothing is claimed for it, which is the whole difference between this and "
           "proceeding on a guess", out)
        ok(seen["reads"] > 1,
           "and it really did ask again rather than refusing on the first UNKNOWN",
           str(seen["reads"]))

        print("\n  -- any claim that does not reach a merge goes back, not only a lost race --")
        # `claim_half` also refuses for a RED check on the claim commit, a push that failed,
        # and a sha it could not read back. None of those is a lost race, and the first
        # version left the claim standing for all three while telling the reader to fix it
        # and run again. A number held by a branch that is not about to land is a number
        # another branch can take from under it.
        red_before = git(gate_repo, "rev-parse", "HEAD").strip()
        out, code, seen = drive_main(gate_repo, mergeable, (None, 0), claims=True,
                                     claim_code=1)
        red_sha = git(gate_repo, "rev-parse", "HEAD").strip()
        ok(code == 1 and seen["rollback"] == [red_sha],
           "a claim half that refuses AFTER committing — a red claim commit, a failed push "
           "— has its claim backed out by sha, where it used to be left standing",
           f"{code} {seen['rollback']} vs {red_sha}")
        ok(red_sha != red_before, "the arm really did move HEAD, so it is not vacuous")

        out, code, seen = drive_main(gate_repo, mergeable, (None, 0), claims=False,
                                     claim_code=1)
        ok(seen["rollback"] == [],
           "and a claim half that refused BEFORE committing backs nothing out — the "
           "rollback is keyed on this run having moved the branch", out)

        print("\n  -- and the backout is a revert of the claim commit, pushed --")
        # THE INVERSE BY THE EXACT ROUTE. `claim_half` refuses a dirty tree before it
        # commits, so the claim commit is the ONLY thing between the branch and its slug
        # form — reverting it restores the heading, the citations, the index, the manifest
        # and the entry's own filename with nothing parsed and nothing reconstructed.
        back = tmp / "backout"
        back.mkdir()
        back_repo = build_split(back)
        with_claimer(back_repo)
        git(back_repo, "add", "-A")
        git(back_repo, "commit", "-qm", "the checkout carries the claimer")
        git(back_repo, "push", "-q", "origin", "main")
        git(back_repo, "checkout", "-q", "-b", "backout-branch")
        b_slug = "D-" + "backed-out"
        write(back_repo, f"docs/decisions/{b_slug}.md", f"## {b_slug} — Backed out\n\nbody\n")
        git(back_repo, "add", "-A")
        git(back_repo, "commit", "-qm", "the branch writes its slug")
        git(back_repo, "push", "-q", "origin", "backout-branch")
        slugged = snapshot(back_repo)
        claim(back_repo, "--root", str(back_repo), "--write")
        git(back_repo, "add", "-A")
        git(back_repo, "commit", "-qm", "Claim the ids this branch left as slugs (D140)")
        git(back_repo, "push", "-q", "origin", "HEAD")
        claim_sha = git(back_repo, "rev-parse", "HEAD").strip()
        ok(snapshot(back_repo) != slugged, "the claim really changed the tree")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            merge_pr_module().rollback_claim(str(back_repo), 77, claim_sha, "backout-branch")
        rolled = buf.getvalue()
        ok(snapshot(back_repo) == slugged,
           "the backout restores the tree BYTE FOR BYTE, filename included",
           "\n".join(sorted(set(slugged) ^ set(snapshot(back_repo)))))
        ok(git(back_repo, "rev-parse", "HEAD").strip() != claim_sha
           and claim_sha in git(back_repo, "log", "--format=%H"),
           "by a REVERT and never a rewrite — the claim commit is already on origin and may "
           "already be somebody's read", rolled)
        ok(git(back_repo, "rev-parse", "HEAD").strip()
           == git(back_repo, "rev-parse", "origin/backout-branch").strip(),
           "and origin carries the backout too, so no claimed number is left standing there",
           rolled)
        ok("main HAS NOT MOVED" in rolled and "merge" in rolled.lower(),
           "it says which it did — backed out, not retried — and what to do next", rolled)

        out, code = claim_rc(back_repo, "--porcelain")
        ok(b_slug in out,
           "and the slug is pending again, so a re-run claims a fresh number", out)

        moved = tmp / "moved"
        moved.mkdir()
        moved_repo = build_split(moved)
        git(moved_repo, "checkout", "-q", "-b", "moved-branch")
        write(moved_repo, "note.md", "a\n")
        git(moved_repo, "add", "-A")
        git(moved_repo, "commit", "-qm", "a commit that is not the claim")
        stale_sha = git(moved_repo, "rev-parse", "HEAD").strip()
        write(moved_repo, "note.md", "b\n")
        git(moved_repo, "add", "-A")
        git(moved_repo, "commit", "-qm", "something moved the branch since")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            merge_pr_module().rollback_claim(str(moved_repo), 77, stale_sha, "moved-branch")
        out = buf.getvalue()
        ok("no longer the claim commit" in out
           and (moved_repo / "note.md").read_text(encoding="utf-8") == "b\n",
           "and it refuses to revert when HEAD is not the commit it was told to undo — a "
           "backout that guesses is the thing this whole file exists to delete", out)

    print("\nclaim self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
