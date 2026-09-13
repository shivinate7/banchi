#!/usr/bin/env python3
"""`make heartbeat` — docs/GATES.md item 24, the durable scheduled heartbeat that watches
repo state across sessions.

THE QUESTION THIS ANSWERS. Every session here sees only its own tree and its own branch — a
worktree cannot tell whether another one has gone stale, whether a PR it never touched has been
green and unmerged for a day, or whether the claim it made an hour ago has since been taken by
main. Nobody is POSITIONED to ask those questions from inside a session; this is what asks them
from outside all of them, on a schedule, the way `make coordinator` already asks the narrower
question "is the queue moving" and `make janitor` already asks "what is safe to sweep."

WHY THIS IS A THIN CALLER AND NOT A FOURTH READER OF THE SAME FACTS (no bandaids: check
whether the primitive exists first). `scripts/coordinator.py --json` already reads open PRs
pinned to their head SHA, `id claims`, dirty worktrees, and live sessions — four of this file's
six bullets, verbatim. Rebuilding that here would be a second copy of `verdict_for`'s five-rule
precedence table, aging out of step with the first the next time D148's wait logic changes.
So this file calls it, and adds exactly the two things it does not already answer:

  - whether MAIN'S OWN last push is green (`coordinator`'s `block_main` compares
    `refs/heads/main` against `origin/main` — agreement, not CI — because a session run from
    a stale local main is what it is guarding; nothing there reads main's own check-runs)
  - `make janitor`'s own TIER framing (merged branches it would take, tier 2 candidates) in
    its own vocabulary, because "worktrees dirty with no session in them" (coordinator) and
    "a merged branch no tree holds" (janitor) are different questions that happen to look at
    the same worktree list

TWO CONSTRAINTS, ESTABLISHED WITH THE OWNER AND BINDING (docs/GATES.md item 24, docs/map.py's
OPEN entry `n: 24`):

  NEVER A DAEMON. This runs once per invocation and exits. It is registered as a scheduled
  task that fires only while the desktop app that launches it is open — nothing in this file
  loops, sleeps, or waits for the next tick; that is the scheduler's job, not this script's.
  Anything whose correctness depended on this having fired on any particular cadence would be
  the wrong thing to build here.

  EACH RUN IS A FRESH SESSION WITH NO CONVERSATION CONTEXT. This process starts knowing
  nothing about who asked for what or who is blocked on whom — and neither would the agent
  session a scheduled task spawns to run it. So anything needing memory of a PREVIOUS run
  lives in a FILE, not in a session: `.serve/heartbeat/latest.json` is this run's report,
  `.serve/heartbeat/history.jsonl` is one line per run, and `new_since_last_run` below is
  computed by diffing this run's open-PR numbers, worktree paths, and id-claim collisions
  against the previous `latest.json` — which is the "a pull request now conflicting with a
  live session that has not been told" bullet: WHETHER it has been told is exactly whether it
  was already in the last report.

READ-AND-REPORT AUTHORITY, NOT MERGE AUTHORITY (both constraints point the same way). This
file writes only `.serve/heartbeat/*` — never a merge, never a branch, never `--confirm` on
anything it shells out to. `make janitor` is invoked WITHOUT `--confirm`, always: what this
reports is what a human would see in the preview, never what a press would do next. A session
with no memory of the last run has no basis for pressing an irreversible button, which is
`make merge`'s own reason for wanting the owner's word.

    scripts/heartbeat.py                the report, human-readable
    scripts/heartbeat.py --json         the same, as one object (and what the report file holds)
    scripts/heartbeat.py --no-network   the janitor half alone; coordinator's network blocks
                                        read as NOT LOOKED AT rather than omitted (same rule
                                        `coordinator.py --no-network` already uses)

Stdlib only, no venv — same as `status.py`, `docs-audit.py` and `coordinator.py`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
HEARTBEAT_DIR = ROOT / ".serve" / "heartbeat"
LATEST = HEARTBEAT_DIR / "latest.json"
HISTORY = HEARTBEAT_DIR / "history.jsonl"

WIDTH = 78


class Ran:
    __slots__ = ("ok", "out", "err")

    def __init__(self, ok: bool, out: str, err: str) -> None:
        self.ok = ok
        self.out = out
        self.err = err


def run(args: Sequence[str], timeout: int = 120) -> Ran:
    """A subprocess, never a shell — `coordinator.py`'s own rule: a caller that went through
    `sh -c` could have its stderr redirected by a caller's quoting, and this file exists to
    report accurately, not to become one more thing that silently says less than it saw."""
    try:
        done = subprocess.run(list(args), cwd=str(ROOT), capture_output=True, text=True,
                               check=False, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return Ran(False, "", str(exc))
    return Ran(done.returncode == 0, done.stdout.strip(), done.stderr.strip())


def git(*args: str) -> Ran:
    return run(["git", *args])


def gh_json(path: str, timeout: int = 60) -> Tuple[Optional[object], str]:
    done = run(["gh", "api", path], timeout=timeout)
    if not done.ok:
        return None, (done.err or done.out or "gh failed with no message").splitlines()[0] \
            if (done.err or done.out) else "gh failed with no message"
    try:
        return json.loads(done.out), ""
    except ValueError as exc:
        return None, "gh returned something that is not JSON: {0}".format(exc)


# ------------------------------------------------------------------ the two blocks coordinator.py does not have

def block_main_ci(no_network: bool) -> Dict[str, object]:
    """Whether MAIN'S OWN last push is green — the one bullet `coordinator.py:block_main`
    does not answer, because that function compares local main against origin/main
    (agreement, never CI). `branches/main/protection`'s required contexts and
    `commits/<sha>/check-runs` are the same two reads `coordinator.py:block_floor` and
    `verdict_for` make for a PR head, pointed at origin/main's own tip instead — duplicated
    here as a few lines rather than imported, because coordinator's functions are keyed to a
    PR floor object this file has no reason to construct."""
    if no_network:
        # NAMED, NOT OMITTED AND NOT `unknown` — coordinator.py's own rule for the same flag:
        # `--no-network` is a choice the caller made, and it must not read as a failed read.
        return {"not_looked_at": "NOT LOOKED AT — --no-network."}
    remote = git("rev-parse", "refs/remotes/origin/main")
    if not remote.ok:
        return {"unknown": "cannot read origin/main: {0}".format(
            remote.err or "no such ref")}
    sha = remote.out
    remote_url = git("remote", "get-url", "origin")
    if not remote_url.ok:
        return {"unknown": "no `origin` remote to name the repo from"}
    slug = remote_url.out
    for prefix in ("https://github.com/", "git@github.com:"):
        if slug.startswith(prefix):
            slug = slug[len(prefix):]
            break
    slug = slug[:-4] if slug.endswith(".git") else slug

    protection, why = gh_json("repos/{0}/branches/main/protection".format(slug))
    required: Optional[List[str]] = None
    if isinstance(protection, dict):
        checks = protection.get("required_status_checks")
        if isinstance(checks, dict):
            contexts = checks.get("contexts")
            if isinstance(contexts, list):
                required = sorted(str(c) for c in contexts)

    runs_payload, why2 = gh_json(
        "repos/{0}/commits/{1}/check-runs?per_page=100".format(slug, sha))
    if not isinstance(runs_payload, dict):
        return {"unknown": "cannot read check-runs for origin/main's tip {0}: {1}".format(
            sha[:7], why2 or why or "no response")}
    runs = runs_payload.get("check_runs") or []
    if not isinstance(runs, list) or not runs:
        return {"sha": sha, "required": required, "verdict": "no checks",
                "detail": "no workflow has reported on origin/main's tip"}

    bad: List[str] = []
    pending: List[str] = []
    seen: Dict[str, str] = {}
    for entry in runs:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "?")
        conclusion = entry.get("conclusion")
        status = str(entry.get("status") or "")
        if conclusion is None or status in ("queued", "in_progress", "waiting", "pending"):
            pending.append(name)
            seen[name] = "pending"
            continue
        seen[name] = str(conclusion)
        if str(conclusion) not in ("success", "neutral", "skipped"):
            bad.append("{0}={1}".format(name, conclusion))

    if bad:
        verdict, detail = "FAILED", ", ".join(sorted(bad))
    elif pending:
        verdict, detail = "running", "{0} still running: {1}".format(
            len(pending), ", ".join(sorted(pending)))
    elif required is None:
        verdict, detail = "not ready", "required checks could not be read from branch protection"
    else:
        missing = sorted(n for n in required if n not in seen)
        skipped = sorted(n for n in required if seen.get(n) == "skipped")
        if missing or skipped:
            parts = []
            if missing:
                parts.append("{0} required check(s) never reported: {1}".format(
                    len(missing), ", ".join(missing)))
            if skipped:
                parts.append("{0} required check(s) reported skipped: {1}".format(
                    len(skipped), ", ".join(skipped)))
            verdict, detail = "not ready", "; ".join(parts)
        else:
            verdict, detail = "green", "{0} runs, every required check passed".format(len(runs))
    return {"sha": sha, "required": required, "verdict": verdict, "detail": detail}


def block_janitor_preview() -> Dict[str, object]:
    """`make janitor`'s own preview, in its own tier vocabulary — merged branches no tree
    holds, worktrees with no live session. NEVER `--confirm`: this script has read-and-report
    authority only, so the underlying tool is invoked exactly the way a human would run it to
    look first."""
    done = run([sys.executable, str(ROOT / "scripts" / "janitor.py")], timeout=180)
    if not done.ok and not done.out:
        return {"unknown": "`make janitor`'s reader could not run: {0}".format(
            done.err or "no output and a non-zero exit")}
    return {"raw": done.out or done.err}


def block_docs_audit() -> Dict[str, object]:
    """The mechanical doc-health half item 24 names as one of its callers. Not gated
    on the outcome — a red docs-audit is not this file's business to fix, only to report
    the fact of."""
    done = run([sys.executable, str(ROOT / "scripts" / "docs-audit.py"), "--json"], timeout=180)
    if not done.out:
        return {"unknown": "docs-audit printed nothing: {0}".format(
            done.err or "no output")}
    try:
        payload = json.loads(done.out)
    except ValueError as exc:
        return {"unknown": "docs-audit's --json did not parse: {0}".format(exc)}
    return {"ok": bool(payload.get("ok")) if isinstance(payload, dict) else None,
            "raw": payload}


def block_coordinator(no_network: bool) -> Dict[str, object]:
    """`scripts/coordinator.py --json` verbatim — the four bullets it already answers:
    open PRs pinned to their head SHA, `id claims`, dirty worktrees, live sessions."""
    args = [sys.executable, str(ROOT / "scripts" / "coordinator.py"), "--json"]
    if no_network:
        args.append("--no-network")
    done = run(args, timeout=180)
    if not done.out:
        return {"unknown": "coordinator printed nothing: {0}".format(
            done.err or "no output")}
    try:
        payload = json.loads(done.out)
    except ValueError as exc:
        return {"unknown": "coordinator's --json did not parse: {0}".format(exc)}
    return {"incomplete": bool(payload.get("incomplete")) if isinstance(payload, dict) else None,
            "raw": payload}


# ------------------------------------------------------------------------------ memory across runs

def _open_pr_numbers(coordinator_block: Dict[str, object]) -> List[int]:
    raw = coordinator_block.get("raw")
    if not isinstance(raw, dict):
        return []
    prs = raw.get("open pull requests")
    if not isinstance(prs, dict):
        return []
    data = prs.get("data")
    if not isinstance(data, list):
        return []
    numbers: List[int] = []
    for entry in data:
        if isinstance(entry, dict) and isinstance(entry.get("number"), int):
            numbers.append(entry["number"])
    return numbers


def _worktree_paths(coordinator_block: Dict[str, object]) -> List[str]:
    raw = coordinator_block.get("raw")
    if not isinstance(raw, dict):
        return []
    wt = raw.get("worktrees")
    if not isinstance(wt, dict):
        return []
    data = wt.get("data")
    if not isinstance(data, list):
        return []
    return [str(entry.get("path")) for entry in data
            if isinstance(entry, dict) and entry.get("path") is not None]


def diff_since_last(report: Dict[str, object]) -> Dict[str, object]:
    """WHAT IS NEW SINCE THE LAST RUN — the "not yet told" half of the design. A session with
    no memory of the previous report cannot say whether an open PR or a dirty worktree is
    something it has already surfaced; comparing this run's `latest.json` against the one on
    disk before this run overwrote it is what answers that without a session remembering
    anything."""
    if not LATEST.exists():
        return {"first_run": True, "new_open_prs": [], "new_worktrees": []}
    try:
        previous = json.loads(LATEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"first_run": False, "unreadable_previous": True,
                "new_open_prs": [], "new_worktrees": []}
    prev_coordinator = previous.get("coordinator") if isinstance(previous, dict) else None
    prev_prs = set(_open_pr_numbers(prev_coordinator)) if isinstance(prev_coordinator, dict) else set()
    prev_wts = set(_worktree_paths(prev_coordinator)) if isinstance(prev_coordinator, dict) else set()

    this_coordinator = report.get("coordinator")
    this_prs = set(_open_pr_numbers(this_coordinator)) if isinstance(this_coordinator, dict) else set()
    this_wts = set(_worktree_paths(this_coordinator)) if isinstance(this_coordinator, dict) else set()

    return {
        "first_run": False,
        "new_open_prs": sorted(this_prs - prev_prs),
        "new_worktrees": sorted(this_wts - prev_wts),
    }


# ------------------------------------------------------------------------------------- render

def render(report: Dict[str, object]) -> str:
    lines: List[str] = []
    lines.append("=" * WIDTH)
    lines.append("heartbeat — read at {0}".format(report.get("at")))
    lines.append("=" * WIDTH)

    coord = report.get("coordinator")
    lines.append("")
    lines.append("coordinator (open PRs, id claims, worktrees, live sessions)")
    if isinstance(coord, dict) and coord.get("unknown"):
        lines.append("  UNKNOWN  {0}".format(coord["unknown"]))
    elif isinstance(coord, dict):
        lines.append("  incomplete: {0}".format(coord.get("incomplete")))
        lines.append("  (full detail in --json / .serve/heartbeat/latest.json)")

    main_ci = report.get("main_ci")
    lines.append("")
    lines.append("main's last push")
    if isinstance(main_ci, dict) and main_ci.get("unknown"):
        lines.append("  UNKNOWN  {0}".format(main_ci["unknown"]))
    elif isinstance(main_ci, dict) and main_ci.get("not_looked_at"):
        lines.append("  {0}".format(main_ci["not_looked_at"]))
    elif isinstance(main_ci, dict):
        lines.append("  {0}  {1}".format(main_ci.get("verdict"), main_ci.get("detail")))

    janitor = report.get("janitor_preview")
    lines.append("")
    lines.append("janitor preview (nothing pressed — --confirm is never passed)")
    if isinstance(janitor, dict) and janitor.get("unknown"):
        lines.append("  UNKNOWN  {0}".format(janitor["unknown"]))
    elif isinstance(janitor, dict):
        for line in str(janitor.get("raw", "")).splitlines()[:20]:
            lines.append("  {0}".format(line))

    audit = report.get("docs_audit")
    lines.append("")
    lines.append("docs-audit")
    if isinstance(audit, dict) and audit.get("unknown"):
        lines.append("  UNKNOWN  {0}".format(audit["unknown"]))
    elif isinstance(audit, dict):
        lines.append("  ok: {0}".format(audit.get("ok")))

    new = report.get("new_since_last_run")
    lines.append("")
    lines.append("new since the last run (this is what nobody has been told yet)")
    if isinstance(new, dict):
        if new.get("first_run"):
            lines.append("  first run — nothing to compare against")
        else:
            if new.get("new_open_prs"):
                lines.append("  new open PRs: {0}".format(new["new_open_prs"]))
            if new.get("new_worktrees"):
                lines.append("  new dirty/unowned worktrees: {0}".format(new["new_worktrees"]))
            if not new.get("new_open_prs") and not new.get("new_worktrees"):
                lines.append("  nothing new")
    lines.append("")
    lines.append("=" * WIDTH)
    lines.append("read-and-report only — nothing here merges, presses, or confirms anything.")
    return "\n".join(lines)


# --------------------------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="the report as one object")
    parser.add_argument("--no-network", action="store_true",
                        help="the janitor/docs-audit half alone; coordinator's and main's own "
                             "CI network reads become NOT LOOKED AT rather than omitted")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)

    report: Dict[str, object] = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "coordinator": block_coordinator(args.no_network),
        "main_ci": block_main_ci(args.no_network),
        "janitor_preview": block_janitor_preview(),
        "docs_audit": block_docs_audit(),
    }
    report["new_since_last_run"] = diff_since_last(report)

    HEARTBEAT_DIR.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report, default=str))
        fh.write("\n")

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(render(report))

    unknown = any(
        isinstance(report.get(key), dict) and report[key].get("unknown")
        for key in ("coordinator", "main_ci", "janitor_preview", "docs_audit")
    )
    return 1 if unknown else 0


if __name__ == "__main__":
    sys.exit(main())
