#!/usr/bin/env python3
"""`make coordinator` — the merge queue, READ rather than remembered.

WHY THIS EXISTS. On 2026-09-12 a coordinator session relayed `#300 GREEN — merging` for
several turns while nothing merged. The line came from a merge driver's stdout, two instances
of that driver were racing, and the `pgrep`-based waiter meant to serialise them was matching
its own command line, so it never fired. The owner caught it by asking: *"feel like 3 have been
left for a while, just confirming you're actually checking."*

THE DEFECT WAS NOT THE DRIVER. It was that the status line was COMPOSED — assembled by a
session out of a tool's stdout and its own memory of what it had started. A composed line can
be a turn stale, or ten, and nothing about reading it says which. So this file removes the
composing: every figure below is read from the repository or from the GitHub API at the moment
you run it, and nothing is read from any local tool's output.

FOUR RULES THIS FILE KEEPS, EACH ONE PAID FOR:

  A VERDICT IS PINNED TO A SHA. `gh pr checks` answers about a pull request; this asks
  `commits/<headRefOid>/check-runs`, so a green from a push three commits ago cannot be
  mistaken for a green on the code that would merge. The SHA is printed beside the verdict for
  exactly that reason.

  A COMMIT SHORT OF THE FLOOR IS `not ready`, NEVER CLEAN. A commit whose checks have not all
  reported yet has every reported check PASSING, which reads as success to anything that looks
  at conclusions alone. That is the whole shape of the incident, and the floor is what refuses
  it.

  THE FLOOR IS A SET OF REQUIRED NAMES AND NOT A COUNT, AND THAT IS A MEASUREMENT RATHER THAN
  A PREFERENCE. A count was the obvious spelling and this file was written with one — derived
  from `origin/main`'s own tip, which looked like the self-updating choice. Measured
  2026-09-12, against the live repository, it is wrong in both directions:

      origin/main tip df6ec79   10 runs — including `build` and `deploy`, which come from
                                `demo.yml` and run ON PUSH TO MAIN ONLY. No pull request can
                                ever reach 10, so every PR would have read `not ready` forever,
                                and a signal that is always on carries nothing.
      PR #309 head 2f9159a       6 runs — with `design-check` as ONE gated run rather than the
                                three shards main carries, because D141 path-gates the browser
                                matrix. So the NAMES move with the change as well as the count.

  So the floor is read from where the requirement actually lives: `branches/main/protection`'s
  required status checks, which on 2026-09-12 are `check` and `revert-guard`. GitHub enforces
  that set, the owner configured it, and it survives both path-gating and matrix expansion.
  A required context that is MISSING is `not ready`; one that reported `skipped` is also `not
  ready`, because a required check that did not run is the definition of nothing being known.
  A floor this file cannot read is reported as unknown and every otherwise-green PR then reads
  `not ready` — the conservative direction, because silence must never render as success.

  `check-suites` WAS TRIED AND IS NOT USABLE, recorded so nobody re-derives it: a permanently
  `queued` suite belonging to the `claude` app sits on merged PR heads with 0 runs, so "every
  suite completed" marks every pull request in the repository as still running.

  `conclusion: null` IS `running`, NEVER `failed`. GitHub reports an in-flight run with a null
  conclusion; reading that as a failure is the mirror of the bug this file is about, and it
  would teach a session to distrust the report.

  LIVENESS IS READ FROM THE CONSOLE APP'S OWN RECORDS, AND THE START TIME IS CHECKED. Two pids
  were recycled into unrelated shells within minutes on 2026-09-12, so a pid alone is not an
  identity — `scripts/janitor.py:_same_process` is the account, and its `startedAt` epoch
  comparison is copied here with its argument rather than re-derived. Never an mtime: a tree
  with no dirty files and no recent writes is indistinguishable from an abandoned one.

IT REACHES THE NETWORK, SO IT IS DELIBERATELY NOT IN `make check`. `make lan-check` is the
precedent and the Makefile comment beside it is the reason in full: `check` answers from the
tree alone, and a row that fails on a train is a row people learn to ignore. What DOES gate is
`make coordinator-selftest`, which runs the verdict rules against synthetic check-run payloads
and needs no network at all — the same split `verdict-selftest` already makes.

NOTHING HERE IS A FACT ABOUT THE PROJECT, which is `scripts/status.py`'s rule and this file
inherits it along with its hardest consequence: ANY BLOCK THIS FILE CANNOT READ PRINTS
`UNKNOWN` WITH THE REASON AND MAKES THE EXIT NON-ZERO. It never omits a block and never
guesses a substitute, because a status tool that silently prints less is worse than no status
tool — you will believe it. That is the same sentence as the guard beside it: a reader must be
able to tell "nothing is wrong" from "nothing is known yet".

Stdlib only, no venv — `python3` and not `$(PYTHON)` in the Makefile, same as `status` and
`docs-audit`.

    scripts/coordinator.py                 the report
    scripts/coordinator.py --json          the same, as one object
    scripts/coordinator.py --no-network     the repository half alone
    scripts/coordinator.py --expect N       also require at least N check runs
    scripts/coordinator.py --selftest       the verdict rules, against synthetic payloads
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
WIDTH = 78

SESSIONS_DIR = Path.home() / ".claude" / "sessions"

# D135's three symlinks and the one untracked Codex file beside them. A worktree carries these
# without having been worked in, and reporting them as uncommitted work would make every tree
# on the machine look dirty — which is the same "a signal that is always on carries nothing"
# failure the rest of this file is about.
D135_NOISE = {
    ".agents", ".agents/", ".agents/skills",
    ".codex", ".codex/", ".codex/config.toml",
    "AGENTS.md", "code-card-fork/AGENTS.md",
}

# ---------------------------------------------------------------------------- the verdicts

GREEN = "green"
FAILED = "FAILED"
RUNNING = "running"
NOT_READY = "not ready"
NO_CHECKS = "no checks"

_BAD = {"failure", "cancelled", "timed_out", "action_required", "startup_failure", "stale"}
_FINE = {"success", "skipped", "neutral"}


class Floor(NamedTuple):
    """What a commit must carry before anything may call it clean.

    `required` is the set of check-run NAMES branch protection insists on; `None` means it
    could not be read, which is never treated as "nothing required". `count` is an optional
    extra minimum on the raw number of runs, only ever set by `--expect`.
    """
    required: Optional[frozenset]
    count: Optional[int] = None
    how: str = ""


class Checks(NamedTuple):
    verdict: str
    total: int
    detail: str


def verdict_for(runs: Sequence[dict], floor: Floor) -> Checks:
    """The check verdict for ONE commit, and the order of precedence is the whole content.

    1. nothing reported at all          -> `no checks`. Not green. A commit no workflow has
                                           touched is the state a session most wants to read
                                           as ready, and it is the furthest thing from it.
    2. something completed badly        -> `FAILED`. Decisive and actionable, so it outranks
                                           everything below it.
    3. something has not finished       -> `running`. A null conclusion is IN FLIGHT. Reading
                                           it as a failure is this file's own bug class
                                           pointed the other way.
    4. the floor is not satisfied       -> `not ready`. Every run that reported passed, and
                                           the ones that have not reported are the ones that
                                           would have caught something. THIS IS THE RULE THE
                                           INCIDENT NEEDED: silence is not success.
    5. otherwise                        -> `green`.
    """
    total = len(runs)
    if total == 0:
        return Checks(NO_CHECKS, 0, "no workflow has reported on this commit")

    bad: List[str] = []
    pending: List[str] = []
    seen: Dict[str, str] = {}
    for run in runs:
        name = str(run.get("name") or "?")
        conclusion = run.get("conclusion")
        status = str(run.get("status") or "")
        if conclusion is None or status in ("queued", "in_progress", "waiting", "pending"):
            pending.append(name)
            seen[name] = "pending"
            continue
        seen[name] = str(conclusion)
        if str(conclusion) in _BAD:
            bad.append("{0}={1}".format(name, conclusion))
        elif str(conclusion) not in _FINE:
            # An unknown conclusion is NOT read as fine. A vocabulary this file has not seen
            # is a thing to look at, never a thing to wave through.
            bad.append("{0}={1}".format(name, conclusion))

    if bad:
        return Checks(FAILED, total, ", ".join(sorted(bad)))
    if pending:
        return Checks(RUNNING, total,
                      "{0} still running: {1}".format(len(pending), ", ".join(sorted(pending))))

    if floor.required is None:
        return Checks(NOT_READY, total,
                      "all {0} reported checks passed, but the required set could not be read "
                      "from branch protection, so this cannot be called clean".format(total))

    # A REQUIRED CONTEXT THAT NEVER REPORTED, AND ONE THAT REPORTED `skipped`, ARE THE SAME
    # ANSWER: nothing is known about it. The second is the one that looks fine from a distance.
    missing = sorted(name for name in floor.required if name not in seen)
    skipped = sorted(name for name in floor.required
                     if seen.get(name) == "skipped")
    if missing or skipped:
        parts = []
        if missing:
            parts.append("{0} required check(s) have not reported: {1}".format(
                len(missing), ", ".join(missing)))
        if skipped:
            parts.append("{0} required check(s) reported `skipped`, which is not a pass: "
                         "{1}".format(len(skipped), ", ".join(skipped)))
        return Checks(NOT_READY, total, "; ".join(parts))

    if floor.count is not None and total < floor.count:
        return Checks(NOT_READY, total,
                      "all {0} reported checks passed and {1} were expected (--expect) — {2} "
                      "have not reported".format(total, floor.count, floor.count - total))

    return Checks(GREEN, total, "{0} runs, all passing, and every required check reported: "
                                "{1}".format(total, ", ".join(sorted(floor.required))))


# ------------------------------------------------------------------------------- the readers

class Ran(NamedTuple):
    ok: bool
    out: str
    err: str


def run(args: Sequence[str], cwd: Optional[str] = None, timeout: int = 60) -> Ran:
    """A subprocess, never a shell. Failure is a value here, not an exception.

    NO SHELL, AND THAT IS NOT STYLE. This file is the answer to a silenced write; a reader
    that went through `sh -c` could have its own stderr redirected by a caller's quoting and
    would then be the same defect one level up.
    """
    try:
        done = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True,
                              check=False, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return Ran(False, "", str(exc))
    return Ran(done.returncode == 0, done.stdout.strip(), done.stderr.strip())


def git(*args: str, cwd: Optional[str] = None) -> Ran:
    return run(["git", *args], cwd=cwd or str(ROOT))


def gh_json(path: str, timeout: int = 60) -> Tuple[Optional[object], str]:
    """One GitHub API read. Returns (payload, reason-it-failed)."""
    done = run(["gh", "api", path], timeout=timeout)
    if not done.ok:
        return None, (done.err or done.out or "gh failed with no message").splitlines()[0]
    try:
        return json.loads(done.out), ""
    except ValueError as exc:
        return None, "gh returned something that is not JSON: {0}".format(exc)


def repo_slug() -> Tuple[str, str]:
    """`owner/name` for the API calls, from the remote rather than from a constant.

    CLAUDE.md's rename is the reason this is derived: the repository is `shivinate7/banchi`
    and the checkout is still `~/Developer/pkmnscan`, deliberately, so a slug inferred from
    the directory name would be wrong and a hard-coded one would be a second place to edit.
    """
    done = git("remote", "get-url", "origin")
    if not done.ok:
        return "", "no `origin` remote: {0}".format(done.err or "git said nothing")
    url = done.out
    match = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
    if not match:
        return "", "cannot read an owner/name out of `{0}`".format(url)
    return match.group(1), ""


# ------------------------------------------------------------------------------ the sections

class Block(NamedTuple):
    """One section of the report. `unknown` is what makes the exit code non-zero."""
    title: str
    lines: List[str]
    unknown: str = ""
    data: object = None


def block_main() -> Block:
    """main's tip, and whether this clone agrees with origin about it."""
    lines: List[str] = []
    local = git("rev-parse", "--short", "refs/heads/main")
    remote = git("rev-parse", "--short", "refs/remotes/origin/main")
    if not remote.ok:
        return Block("main", [], "cannot read origin/main: {0}".format(
            remote.err or "no such ref — has this clone ever fetched?"))
    lines.append("origin/main   {0}".format(remote.out))
    if not local.ok:
        lines.append("local main    absent in this clone — nothing to compare")
        agree: Optional[bool] = None
    else:
        agree = local.out == remote.out
        lines.append("local main    {0}{1}".format(
            local.out, "" if agree else "  DIFFERS from origin/main"))
        if not agree:
            behind = git("rev-list", "--count", "refs/heads/main..refs/remotes/origin/main")
            ahead = git("rev-list", "--count", "refs/remotes/origin/main..refs/heads/main")
            if behind.ok and ahead.ok:
                lines.append("              {0} behind, {1} ahead".format(behind.out, ahead.out))
    head = git("rev-parse", "--short", "HEAD")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if head.ok and branch.ok:
        lines.append("this tree     {0} on {1}".format(head.out, branch.out))
    return Block("main", lines, "",
                 {"origin_main": remote.out,
                  "local_main": local.out if local.ok else None,
                  "agree": agree})


def block_floor(slug: str, override: Optional[int]) -> Tuple[Block, Floor]:
    """The floor, read from GitHub's own required status checks on `main`.

    NOT FROM A WORKFLOW FILE AND NOT FROM A COUNT. `check.yml` expands a matrix and D141
    path-gates part of it, so the number and the names of a commit's check runs both move with
    the change — the docstring at the top of this file carries the two measurements. What does
    not move is the set branch protection ENFORCES, which is also the only floor whose
    authority is not this file's opinion.
    """
    payload, why = gh_json("repos/{0}/branches/main/protection".format(slug))
    required: Optional[frozenset] = None
    lines: List[str] = []
    unknown = ""
    if payload is None or not isinstance(payload, dict):
        unknown = ("cannot read main's branch protection ({0}), so the required set is "
                   "unknown and every verdict below will say `not ready` rather than "
                   "`green`".format(why))
    else:
        block = payload.get("required_status_checks") or {}
        contexts = block.get("contexts") if isinstance(block, dict) else None
        if not isinstance(contexts, list) or not contexts:
            unknown = ("main's branch protection names no required status checks, so there is "
                       "no floor to measure against and nothing here may read as `green`. Set "
                       "them on GitHub, or pass --expect N to floor on a raw count instead.")
        else:
            required = frozenset(str(name) for name in contexts)
            lines.append("required      {0}".format(", ".join(sorted(required))))
            lines.append("              from branches/main/protection — GitHub enforces this "
                         "set, so it")
            lines.append("              cannot drift from what a merge actually needs")
    if override is not None:
        lines.append("count         >= {0}  (given with --expect)".format(override))
    if unknown:
        return Block("check floor", [], unknown), Floor(None, override, "unreadable")
    return (Block("check floor", lines, "",
                  {"required": sorted(required or []), "count": override,
                   "how": "branches/main/protection"}),
            Floor(required, override, "branches/main/protection"))


def block_open_prs(slug: str, floor: Floor) -> Block:
    """Every open pull request, with a SHA-pinned verdict."""
    done = run(["gh", "pr", "list", "--state", "open", "--limit", "60", "--json",
                "number,title,mergeable,headRefOid,isDraft,author,updatedAt"])
    if not done.ok:
        return Block("open pull requests", [], "cannot list them: {0}".format(
            (done.err or "gh failed").splitlines()[0]))
    try:
        prs = json.loads(done.out or "[]")
    except ValueError as exc:
        return Block("open pull requests", [], "gh returned something unparseable: {0}".format(exc))
    if not prs:
        return Block("open pull requests", ["none"], "", [])

    lines: List[str] = []
    data: List[dict] = []
    unreadable: List[str] = []
    for pr in sorted(prs, key=lambda p: p.get("number") or 0):
        number = pr.get("number")
        sha = str(pr.get("headRefOid") or "")
        title = str(pr.get("title") or "")[:52]
        mergeable = str(pr.get("mergeable") or "UNKNOWN")
        payload, why = gh_json(
            "repos/{0}/commits/{1}/check-runs?per_page=100".format(slug, sha))
        if payload is None or not isinstance(payload, dict):
            # THE ONE THING THIS FILE MAY NOT DO IS GUESS. An unreadable verdict is reported
            # as unreadable and makes the whole run exit non-zero, so a session cannot relay
            # this report as complete.
            lines.append("#{0:<5} {1}".format(number, title))
            lines.append("      {0}  UNKNOWN — {1}".format(sha[:7], why))
            unreadable.append("#{0}".format(number))
            continue
        runs = payload.get("check_runs") or []
        checks = verdict_for([r for r in runs if isinstance(r, dict)], floor)
        flags = []
        if pr.get("isDraft"):
            flags.append("draft")
        if mergeable != "MERGEABLE":
            flags.append("mergeable={0}".format(mergeable))
        lines.append("#{0:<5} {1}{2}".format(
            number, title, "  [" + ", ".join(flags) + "]" if flags else ""))
        lines.append("      {0}  {1:<10} {2}".format(sha[:7], checks.verdict, checks.detail))
        data.append({"number": number, "head": sha, "mergeable": mergeable,
                     "verdict": checks.verdict, "total": checks.total,
                     "detail": checks.detail})
    unknown = ""
    if unreadable:
        unknown = "the check verdict could not be read for {0}".format(", ".join(unreadable))
    return Block("open pull requests", lines, unknown, data)


def block_merged_24h(slug: str) -> Block:
    """How many pull requests merged in the last twenty-four hours."""
    done = run(["gh", "pr", "list", "--state", "merged", "--limit", "100", "--json",
                "number,mergedAt,title"])
    if not done.ok:
        return Block("merged in 24h", [], "cannot list merged PRs: {0}".format(
            (done.err or "gh failed").splitlines()[0]))
    try:
        prs = json.loads(done.out or "[]")
    except ValueError as exc:
        return Block("merged in 24h", [], "gh returned something unparseable: {0}".format(exc))
    cutoff = time.time() - 24 * 3600
    recent: List[int] = []
    for pr in prs:
        stamp = str(pr.get("mergedAt") or "")
        if not stamp:
            continue
        try:
            # `2026-09-12T04:11:52Z`, which is the only shape gh emits here.
            when = time.mktime(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
        except ValueError:
            continue
        if when >= cutoff:
            recent.append(int(pr.get("number") or 0))
    lines = ["{0} merged".format(len(recent))]
    if recent:
        lines.append("                " + ", ".join("#{0}".format(n) for n in sorted(recent)))
    return Block("merged in 24h", lines, "", {"count": len(recent), "numbers": sorted(recent)})


def block_id_claims() -> Block:
    """`id claims`, read out of the audit rather than restated.

    D140's slugs are allocated at the merge, so a coordinator that does not look at this is
    one that can merge two branches claiming the same number.
    """
    done = run(["python3", str(ROOT / "scripts" / "docs-audit.py"), "--json"], timeout=180)
    if not done.out:
        return Block("id claims", [], "docs-audit printed nothing: {0}".format(
            (done.err or "no message").splitlines()[0] if done.err else "no message"))
    try:
        report = json.loads(done.out)
    except ValueError as exc:
        return Block("id claims", [], "docs-audit's --json did not parse: {0}".format(exc))
    rows = report.get("rows") if isinstance(report, dict) else None
    if not isinstance(rows, list):
        return Block("id claims", [], "docs-audit's --json has no `rows`; the reader has gone "
                                      "stale and must be fixed rather than dropped")
    for row in rows:
        if isinstance(row, dict) and row.get("label") == "id claims":
            findings = row.get("findings") or []
            lines = [str(row.get("summary") or "")]
            for finding in findings[:6]:
                if isinstance(finding, dict):
                    lines.append("                {0}".format(
                        str(finding.get("where") or "")))
            return Block("id claims", lines, "",
                         {"summary": row.get("summary"), "findings": len(findings)})
    return Block("id claims", [], "docs-audit ran and reported no `id claims` row at all — "
                                  "the row was renamed or deleted, and this reader is now "
                                  "blind rather than merely quiet")


def _worktrees() -> List[str]:
    done = git("worktree", "list", "--porcelain")
    if not done.ok:
        return []
    return [line.split(" ", 1)[1] for line in done.out.splitlines()
            if line.startswith("worktree ")]


def block_worktrees() -> Block:
    """Every worktree of this clone, and whether it holds uncommitted work."""
    trees = _worktrees()
    if not trees:
        return Block("worktrees", [], "`git worktree list` could not be read")
    lines: List[str] = []
    data: List[dict] = []
    for tree in trees:
        status = git("status", "--porcelain", cwd=tree)
        branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=tree)
        if not status.ok:
            lines.append("{0}".format(tree))
            lines.append("      UNKNOWN — {0}".format(status.err or "git status failed"))
            data.append({"path": tree, "dirty": None})
            continue
        dirty = []
        for line in status.out.splitlines():
            path = line[3:].strip().strip('"')
            if line[:2] == "??" and path.rstrip("/") in {p.rstrip("/") for p in D135_NOISE}:
                continue
            dirty.append(path)
        lines.append("{0}  [{1}]".format(tree, branch.out if branch.ok else "?"))
        lines.append("      {0}".format(
            "clean" if not dirty else "{0} uncommitted: {1}".format(
                len(dirty), ", ".join(dirty[:5]) + (" …" if len(dirty) > 5 else ""))))
        data.append({"path": tree, "branch": branch.out if branch.ok else None,
                     "dirty": len(dirty)})
    return Block("worktrees", lines, "", data)


def _proc_start(pid: int) -> Optional[float]:
    """A pid's start time as an epoch. `janitor.py:_proc_start`'s job, same reason."""
    done = run(["ps", "-o", "lstart=", "-p", str(pid)], timeout=10)
    if not done.ok or not done.out:
        return None
    try:
        return time.mktime(time.strptime(done.out.strip(), "%a %b %d %H:%M:%S %Y"))
    except (ValueError, OverflowError):
        return None


def _same_process(record: dict, pid: int) -> bool:
    """Copied from `scripts/janitor.py:_same_process` WITH ITS ARGUMENT, not re-derived.

    It compares `startedAt` epoch milliseconds and never the `procStart` string beside it: the
    record renders UTC and `ps` renders local, so on this machine every pair differed by
    exactly five hours with identical seconds, and every session was judged dead. Anything
    unreadable resolves to LIVE, because a false "live" reports a session that has finished
    and a false "dead" hides one that is running.
    """
    started = record.get("startedAt")
    if not isinstance(started, (int, float)):
        return True
    actual = _proc_start(pid)
    if actual is None:
        return True
    return abs(actual - started / 1000.0) <= 120.0


def block_sessions(sessions_dir: Path) -> Block:
    """Every live session and the tree it is standing in, from the console app's own records."""
    if not sessions_dir.is_dir():
        return Block("live sessions", [], "{0} is not a directory, so liveness cannot be read "
                                          "at all — and it must NOT be guessed from mtimes or "
                                          "from a pid noted earlier".format(sessions_dir))
    live: List[Tuple[int, str, str]] = []
    for path in sorted(sessions_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        pid, cwd = record.get("pid"), record.get("cwd")
        if not isinstance(pid, int) or not isinstance(cwd, str) or not cwd:
            continue
        try:
            os.kill(pid, 0)
        except OSError:
            continue
        if not _same_process(record, pid):
            continue
        live.append((pid, cwd, str(record.get("name") or "")))
    lines = ["{0} live".format(len(live))]
    for pid, cwd, name in sorted(live):
        lines.append("      pid {0:<7} {1}{2}".format(pid, cwd, "  " + name if name else ""))
    return Block("live sessions", lines, "",
                 [{"pid": p, "cwd": c, "name": n} for p, c, n in sorted(live)])


def block_processes() -> Block:
    """Waiter loops and duplicated drivers, because both were real on 2026-09-12.

    READ-ONLY, AND IT SIGNALS NOTHING. `make reap` is the only thing in this repo that stops a
    process, and `scripts/reap.py --hook` is what refuses a kill whose target is not this
    session's. This block exists because the second half of the incident was invisible: a
    `pgrep -f "<pattern>"` waiter matches ITS OWN command line, so `until ! pgrep -f …` never
    exits, and two copies of a driver raced with nothing reporting that there were two.
    """
    done = run(["ps", "-Ao", "pid=,command="], timeout=30)
    if not done.ok:
        return Block("processes", [], "`ps` could not be read: {0}".format(done.err or "?"))

    known = {p.name for p in (ROOT / "scripts").glob("*") if p.is_file()}
    waiters: List[str] = []
    by_path: Dict[str, List[int]] = {}
    for line in done.out.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        pid, command = int(parts[0]), parts[1]
        if "pgrep" in command and re.search(r"\b(until|while)\b", command):
            waiters.append("pid {0}  {1}".format(pid, command[:88]))
        for token in command.split():
            if not token.startswith("/") or not token.endswith((".py", ".sh", ".mjs")):
                continue
            # GROUPED BY THE ABSOLUTE PATH AND NEVER BY THE BASENAME, which is a correction
            # this block earned on its first real run. Four `serve.py` processes were live —
            # the main checkout's supervisor, one worktree's, and two temp trees from
            # concurrent `serve-selftest` runs — and a basename count called that DUPLICATED.
            # It is not: D43 gives every checkout its own server, so four is the CORRECT
            # number and a block that reports it is a block nobody reads. Two instances of
            # the SAME path is the defect the 2026-09-12 incident actually was.
            #
            # Scoped by basename to this checkout's own tools, so a temp tree's copy still
            # counts while the user's unrelated projects do not.
            if token.rsplit("/", 1)[-1] in known:
                by_path.setdefault(token, []).append(pid)

    lines: List[str] = []
    for waiter in waiters:
        lines.append("WAITER LOOP   {0}".format(waiter))
        lines.append("              a `pgrep -f` waiter matches its own command line, so this "
                     "may never exit")
    duplicated = {path: sorted(set(pids)) for path, pids in by_path.items()
                  if len(set(pids)) > 1 and not path.endswith("/coordinator.py")}
    for path, pids in sorted(duplicated.items()):
        lines.append("DUPLICATED    {0} instances of ONE script: {1}".format(len(pids), path))
        lines.append("              pids {0} — two copies of one driver is what raced on "
                     "2026-09-12".format(", ".join(str(p) for p in pids)))
    if not lines:
        lines.append("no waiter loops, and no script running twice from one path")
    return Block("processes", lines, "",
                 {"waiters": len(waiters), "duplicated": duplicated})


# -------------------------------------------------------------------------------- the render

def render(blocks: Sequence[Block]) -> int:
    print("=" * WIDTH)
    print("coordinator — read at {0}".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    print("=" * WIDTH)
    unknown = 0
    for block in blocks:
        print("")
        print("{0}".format(block.title))
        if block.unknown:
            unknown += 1
            print("  UNKNOWN  {0}".format(block.unknown))
            continue
        for line in block.lines:
            print("  {0}".format(line))
    print("")
    print("=" * WIDTH)
    if unknown:
        # THE WHOLE POINT, ONE LAST TIME. A report with a hole in it is not a report, and a
        # session that relays it as one has made the 2026-09-12 mistake in a new place.
        print("{0} block(s) could not be read. THIS REPORT IS INCOMPLETE — do not relay it "
              "as the".format(unknown))
        print("state of the queue. Fix the reader or say which block is unknown.")
        return 1
    print("every block read.")
    return 0


# ------------------------------------------------------------------------------- the selftest

def selftest() -> int:
    """The verdict rules, against synthetic check-run payloads. No network, so this gates.

    IT PROVES THE RULES BY VIOLATING THEM: each case is a payload that a reader looking at
    conclusions alone would call clean, and the assertion is that this one does not.
    """
    # THE REAL REQUIRED SET, as `branches/main/protection` reported it on 2026-09-12. Using
    # the live names rather than `a`/`b` is what makes these cases readable as the repository's
    # own situation instead of as arithmetic.
    REQ = Floor(frozenset({"check", "revert-guard"}), None, "fixture")
    NONE = Floor(None, None, "unreadable")

    def ok(name, conclusion="success", status="completed"):
        return {"name": name, "status": status, "conclusion": conclusion}

    cases = [
        ("both required checks passed, plus the optional ones",
         [ok("check"), ok("revert-guard"), ok("browser-scope"), ok("design-check")],
         REQ, GREEN),
        ("`revert-guard` has not reported — silence is NOT success",
         [ok("check"), ok("browser-scope"), ok("design-check"), ok("already-passed")],
         REQ, NOT_READY),
        ("one required check of two, everything reported passing: the incident's shape",
         [ok("check")], REQ, NOT_READY),
        ("zero runs is not green",
         [], REQ, NO_CHECKS),
        ("a required check that reported `skipped` is not a pass",
         [ok("check"), ok("revert-guard", "skipped")], REQ, NOT_READY),
        ("an OPTIONAL check may be skipped — main's own design-check-passed",
         [ok("check"), ok("revert-guard"), ok("design-check-passed", "skipped")],
         REQ, GREEN),
        ("a null conclusion is RUNNING, never failed",
         [ok("check"), ok("revert-guard", None, "in_progress")], REQ, RUNNING),
        ("an in_progress run with a conclusion already set is still running",
         [ok("check"), ok("revert-guard", "success", "in_progress")], REQ, RUNNING),
        ("a queued run is running",
         [ok("check"), ok("revert-guard", None, "queued")], REQ, RUNNING),
        ("a failure is FAILED",
         [ok("check", "failure"), ok("revert-guard")], REQ, FAILED),
        ("a failure outranks a missing required check",
         [ok("check", "failure")], REQ, FAILED),
        ("a cancelled run is FAILED",
         [ok("check", "cancelled"), ok("revert-guard")], REQ, FAILED),
        ("a timed_out run is FAILED",
         [ok("check", "timed_out"), ok("revert-guard")], REQ, FAILED),
        ("a neutral run passes",
         [ok("check", "neutral"), ok("revert-guard")], REQ, GREEN),
        ("a conclusion this file has never seen is NOT waved through",
         [ok("check", "something_new"), ok("revert-guard")], REQ, FAILED),
        ("an unreadable required set can never read clean",
         [ok("check"), ok("revert-guard")], NONE, NOT_READY),
        ("an unreadable required set still reports a real failure",
         [ok("check", "failure")], NONE, FAILED),
        ("an unreadable required set still reports running",
         [ok("check", None, "in_progress")], NONE, RUNNING),
        ("--expect floors on the raw count as well",
         [ok("check"), ok("revert-guard")],
         Floor(frozenset({"check", "revert-guard"}), 6, "fixture"), NOT_READY),
        ("--expect satisfied, and the required set too",
         [ok("check"), ok("revert-guard"), ok("c"), ok("d"), ok("e"), ok("f")],
         Floor(frozenset({"check", "revert-guard"}), 6, "fixture"), GREEN),
    ]
    passed = failed = 0
    print("coordinator-selftest — the verdict rules, no network")
    print("")
    for label, runs, floor, want in cases:
        got = verdict_for(runs, floor).verdict
        if got == want:
            passed += 1
            print("  ok     {0}".format(label))
        else:
            failed += 1
            print("  FAIL   {0} — wanted `{1}`, got `{2}`".format(label, want, got))

    # A BLOCK THAT CANNOT BE READ MUST MAKE THE EXIT NON-ZERO. That is the report's half of the
    # same invariant, and it is what stops a session relaying a partial answer as a whole one.
    # `render` is run for its EXIT CODE, with its output swallowed — the one place in this
    # repo where discarding a command's output is the point rather than the defect, because
    # what is being asserted is the code and the text is the fixture's noise.
    def code_for(blocks: Sequence[Block]) -> int:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            return render(blocks)

    if code_for([Block("a readable block", ["fine"]),
                 Block("an unreadable block", [], "the reason it could not be read")]) == 1:
        passed += 1
        print("  ok     an UNKNOWN block makes the report exit non-zero")
    else:
        failed += 1
        print("  FAIL   an UNKNOWN block did not make the report exit non-zero")

    if code_for([Block("a readable block", ["fine"])]) == 0:
        passed += 1
        print("  ok     a complete report exits zero")
    else:
        failed += 1
        print("  FAIL   a complete report did not exit zero")

    print("")
    print("  {0} passed, {1} failed".format(passed, failed))
    return 0 if failed == 0 else 1


# ------------------------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coordinator",
        description="The merge queue, read from the repository and from GitHub.")
    parser.add_argument("--json", action="store_true", help="the report as one object")
    parser.add_argument("--no-network", action="store_true",
                        help="the repository half alone; the GitHub blocks are reported as "
                             "skipped rather than silently missing")
    parser.add_argument("--expect", type=int, default=None,
                        help="also require at least N check runs, on top of the required set read from branch protection")
    parser.add_argument("--selftest", action="store_true",
                        help="the verdict rules, against synthetic payloads. No network.")
    parser.add_argument("--sessions", default="",
                        help="read the liveness oracle elsewhere, for a self-test")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.selftest:
        return selftest()

    sessions = Path(args.sessions) if args.sessions else SESSIONS_DIR
    blocks: List[Block] = [block_main()]

    if args.no_network:
        # NAMED, NOT OMITTED. `--no-network` is a choice the caller made, so it is not an
        # UNKNOWN — but the report still has to say the queue was not looked at, or it reads
        # as "no open PRs".
        blocks.append(Block("open pull requests", [
            "NOT LOOKED AT — --no-network. This is not `none`."]))
        blocks.append(Block("merged in 24h", ["NOT LOOKED AT — --no-network."]))
    else:
        slug, why = repo_slug()
        if not slug:
            blocks.append(Block("open pull requests", [], why))
            blocks.append(Block("merged in 24h", [], why))
        else:
            floor_block, floor = block_floor(slug, args.expect)
            blocks.append(floor_block)
            blocks.append(block_open_prs(slug, floor))
            blocks.append(block_merged_24h(slug))

    blocks.append(block_id_claims())
    blocks.append(block_worktrees())
    blocks.append(block_sessions(sessions))
    blocks.append(block_processes())

    if args.json:
        payload = {block.title: ({"unknown": block.unknown} if block.unknown
                                 else {"data": block.data, "lines": block.lines})
                   for block in blocks}
        payload["incomplete"] = any(block.unknown for block in blocks)
        print(json.dumps(payload, indent=2, default=str))
        return 1 if payload["incomplete"] else 0
    return render(blocks)


if __name__ == "__main__":
    sys.exit(main())
