#!/usr/bin/env python3
"""`make subagent-override-selftest` — the `subagent override` row, proved by violating it.

WHY THIS EXISTS. The row's whole claim is that it can tell a subagent-model override that is
"set on purpose, right now" from one that is forgotten, and that its discovery reaches a
nested git worktree's own settings file — the exact place the 2026-09-19 incident sat, which a
reader of only the checkout root would have missed. This repo's standard for that kind of claim
is reproduction (`guard-shell-selftest.sh`, `reap-selftest.sh`, `janitor-selftest.sh`): build a
real throwaway git repository, add a REAL nested worktree with `git worktree add` — the same
mechanism Claude Code uses for `.claude/worktrees/<name>/` — and only then ask the row about it.

THE CASES, EACH RUN AGAINST THE REAL FIXTURE:

  1. no settings files at all                                        -> green
  2. the override in the checkout's OWN settings.local.json,
     no expiry                                                       -> red, file named
  3. the override in the NESTED WORKTREE's settings.local.json,
     no expiry — the 2026-09-19 shape exactly                        -> red, file named
  4. the same file, an expiry already in the past                    -> red, "in the past"
  5. the same file, an expiry inside the lookahead ceiling            -> GREEN — the case that
     proves this is not a bare forbid: a live, current, dated override is quiet
  6. the same file, an expiry past the lookahead ceiling              -> red, "standing"
  7. the override in the TRACKED settings.json, WITH a valid,
     current expiry                                                  -> red anyway — no
     expiry excuses a committed override, ever

Case 5 against cases 2/3/4/6/7 is the actual proof this task asked for: the same mechanism,
the same file, red on one side of "current" and quiet on the other.

WHY IT IS NOT IN THE GIT HOOK. D18: it writes a temporary git repository and a real worktree.
It IS in `make check` and `make ci-check`, in the guard-selftest section at the end (D161).

WHAT IT CANNOT PROVE. That a session actually writes `CLAUDE_CODE_SUBAGENT_MODEL_UNTIL` when
it sets the override — that half is a habit this repo can argue for and cannot enforce, because
the write happens one directory up, in the owner's own global tooling. This proves the READER
the owner's rule was missing; it does not (and cannot) reach into the writer.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS_AUDIT = HERE / "docs-audit.py"

pass_count = 0
fail_count = 0


def say(tag: str, message: str) -> None:
    print(f"  {tag:<6} {message}")


def ok(message: str) -> None:
    global pass_count
    pass_count += 1
    say("ok", message)


def bad(message: str, detail: str = "") -> None:
    global fail_count
    fail_count += 1
    say("FAIL", message)
    if detail:
        print(f"         {detail}")


def git(args, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def load_docs_audit():
    """Import scripts/docs-audit.py by path, exactly as the audit's own header says a
    read-only tool should NOT be read — by `ast`, never `import` — for OTHER files. This is
    different: it is this row's own module, already trusted to run (the pre-commit hook
    already executes it as `python3 scripts/docs-audit.py --staged`), and importing it in
    a subprocess of its own is the only way to call its pure functions directly.
    """
    if not DOCS_AUDIT.exists():
        print("no docs-audit.py beside this script")
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("docs_audit_selftest", DOCS_AUDIT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_env(path: Path, env: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"env": env}), encoding="utf-8")


def run_row(mod, root: Path):
    """One fresh Report() over the fixture `root`, with ROOT patched and the worktree
    cache cleared so a case run after the previous one sees the disk as it is NOW."""
    saved_root = mod.ROOT
    mod.nested_worktrees.cache_clear()
    try:
        # `.resolve()`, matching the real `ROOT = Path(__file__).resolve().parent.parent`
        # exactly. `nested_worktrees()` reports resolved paths (git resolves symlinks in
        # its own output), and on macOS `/tmp` is itself a symlink to `/private/tmp` — an
        # unresolved fixture root disagreed with its own nested worktree's resolved path
        # and `rel()` fell back to printing the absolute path instead of failing loudly,
        # which is precisely the kind of silent miss this row exists to not have.
        mod.ROOT = root.resolve()
        report = mod.Report()
        mod.check_subagent_override(report)
    finally:
        mod.ROOT = saved_root
        mod.nested_worktrees.cache_clear()
    row = next(r for r in report.checks if r.check == "subagent override")
    return row


def main() -> int:
    mod = load_docs_audit()

    tmp = Path(tempfile.mkdtemp(prefix="pkmnscan-subagent-"))
    try:
        work = tmp / "work"
        git(["init", "-q", "-b", "main", str(work)], cwd=tmp)
        (work / "README.md").write_text("fixture\n", encoding="utf-8")
        git(["-C", str(work), "add", "README.md"], cwd=tmp)
        git(["-C", str(work), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "seed"], cwd=work)

        nested = work / ".claude" / "worktrees" / "other"
        git(["-C", str(work), "worktree", "add", "-q", str(nested), "-b", "other-branch"],
            cwd=work)

        own_local = work / ".claude" / "settings.local.json"
        own_tracked = work / ".claude" / "settings.json"
        nested_local = nested / ".claude" / "settings.local.json"

        override = {
            "CLAUDE_CODE_SUBAGENT_MODEL": "opus",
            "CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1",
        }
        now = datetime.now(timezone.utc)

        # --- case 1: clean tree, no override anywhere -----------------------------------
        row = run_row(mod, work)
        if not row.findings:
            ok("clean tree (own settings + a real nested worktree, no override): green")
        else:
            bad("clean tree should be green", str(row.findings))

        if row.scanned == 4:
            ok("discovery found all 4 candidate files: own settings.json + "
               "settings.local.json, nested worktree's settings.json + settings.local.json")
        else:
            bad(f"expected 4 settings-file candidates (own x2 + nested worktree's x2), "
                f"got {row.scanned}")

        # --- case 2: the override in the checkout's OWN settings.local.json, no expiry --
        write_env(own_local, override)
        row = run_row(mod, work)
        named = any(".claude/settings.local.json" in f.where and "worktrees" not in f.where
                    for f in row.findings)
        if len(row.findings) == 1 and named:
            ok("override in the checkout's own settings.local.json, no expiry: red, named")
        else:
            bad("own settings.local.json with an undated override should be red and named",
                str(row.findings))
        own_local.unlink()

        # --- case 3: the override in the NESTED WORKTREE's settings.local.json, no expiry,
        #     the 2026-09-19 shape exactly — THE CASE THIS ROW EXISTS FOR ------------------
        write_env(nested_local, override)
        row = run_row(mod, work)
        named = any(
            f.where == ".claude/worktrees/other/.claude/settings.local.json"
            for f in row.findings
        )
        if len(row.findings) == 1 and named:
            ok("override in a NESTED WORKTREE's settings.local.json, no expiry: red, and "
               "the finding names that exact nested path — a root-only reader would have "
               "reported this tree as clean")
        else:
            bad("a nested worktree's undated override should be red and named by its own "
                "path, not folded into a generic finding", str(row.findings))

        # --- case 4: same file, an expiry already in the past ---------------------------
        expired = (now - timedelta(hours=3)).isoformat()
        write_env(nested_local, {**override, "CLAUDE_CODE_SUBAGENT_MODEL_UNTIL": expired})
        row = run_row(mod, work)
        if len(row.findings) == 1 and "in the past" in row.findings[0].message:
            ok("nested override with an expiry already in the past: red, named as expired")
        else:
            bad("an expired override should be red and say so", str(row.findings))

        # --- case 5: same file, an expiry inside the lookahead ceiling — THE CURRENT CASE
        current = (now + timedelta(hours=2)).isoformat()
        write_env(nested_local, {**override, "CLAUDE_CODE_SUBAGENT_MODEL_UNTIL": current})
        row = run_row(mod, work)
        if not row.findings:
            ok("nested override with an expiry 2 hours out (inside the ceiling): GREEN — "
               "set on purpose, right now, and the row stays quiet about it")
        else:
            bad("a live, current, dated override should be green, not merely advisory",
                str(row.findings))

        # --- case 6: same file, an expiry past the lookahead ceiling ---------------------
        far = (now + timedelta(hours=72)).isoformat()
        write_env(nested_local, {**override, "CLAUDE_CODE_SUBAGENT_MODEL_UNTIL": far})
        row = run_row(mod, work)
        if len(row.findings) == 1 and "standing" in row.findings[0].message:
            ok("nested override with a 72-hour expiry (past the 24h ceiling): red, named "
               "as reading like a standing exemption")
        else:
            bad("an expiry past the lookahead ceiling should be red", str(row.findings))

        nested_local.unlink()

        # --- case 7: the override in the TRACKED settings.json, with a CURRENT, valid
        #     expiry — no expiry excuses a committed override -----------------------------
        write_env(own_tracked, {**override, "CLAUDE_CODE_SUBAGENT_MODEL_UNTIL": current})
        row = run_row(mod, work)
        if len(row.findings) == 1 and "TRACKED" in row.findings[0].message:
            ok("override in the TRACKED settings.json, with a currently-valid expiry: red "
               "anyway — an expiry never excuses committing the override")
        else:
            bad("a tracked settings.json override must be red regardless of expiry",
                str(row.findings))
        own_tracked.unlink()

        # --- case 8: back to clean, one more time, proving nothing was left behind -------
        row = run_row(mod, work)
        if not row.findings:
            ok("tree returned to clean after every case: green again")
        else:
            bad("tree should be clean after every fixture was removed", str(row.findings))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print(f"{pass_count} passed, {fail_count} failed")
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
