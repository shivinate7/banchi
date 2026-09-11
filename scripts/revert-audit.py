#!/usr/bin/env python3
"""A merge can undo a ruling without anybody writing a line, and this is the reader for that.

WHY THIS EXISTS. `4bf5a44` (PR #218, D119, 2026-09-07) deleted `LocationCard` from
`app/src/Inventory.tsx` and re-pointed the specs that had asserted it. The next commit on main,
`9439765` (PR #221, "The cap is a ceiling on copies live", 2026-09-08), is a single-parent
commit whose tree carried the PRE-deletion copy of all ten front-end files #218 had touched.
Its message was about `--cap` wording; the revert was invisible. Every guard for the deletion
lived in the files that came back, so `make check` and the Playwright suite were green on
both sides, and three days later a session found the component, read the owner's screenshot
of it as a wish, and wrote that down. The likely mechanism: the #221 session merged main into
its branch, resolved the conflicts by keeping "ours", then squashed onto main as one commit.

So this script asks one question of a commit, and asks it two ways:

    DOES THIS COMMIT PUT A FILE BACK THE WAY IT WAS BEFORE AN EARLIER COMMIT MOVED IT?

  whole-file   the commit changes F from blob a to blob b, and a commit within the last N
               first-parent commits changed F from b to a. Exact, by object id, no diff.
  hunk         a `-U0` hunk of the commit on F is, line for line, the reverse of a hunk an
               earlier commit within the window introduced on F. Catches a partial reversal
               buried among real edits.

A reversal is not a defect — `git revert` exists — so a hit is REPORTED with whether the
commit's own message names the file, and the guard (`branch` mode) refuses only a reversal in
a file no commit on the branch names. A branch that means to put something back says so in
a commit message, by file name, and passes.

THREE MODES, ONE ENGINE:

    revert-audit.py history [--window N] [--since REV] [--all] [--show] [--no-gh] [--json]
        Walk first-parent main and report every reversal. `--all` includes hits the commit's
        message accounts for; `--show` prints the reversed hunks; `--no-gh` skips the PR lookup.

    revert-audit.py branch [--upstream origin/main] [--window N]
        THE GUARD. Compute what this branch would land on upstream — the clean merge's tree
        against upstream, or the branch's diff off the merge-base when the merge conflicts —
        and refuse if it reverses something upstream has, in a file the branch's commits never
        name. Exit 1 on a refusal, 0 otherwise, and `PKMNSCAN_REVERT=off` runs nothing and is
        printed in every refusal. This is what `make revert-guard`, the pre-push hook and the
        CI job run.

    revert-audit.py selftest
        Recreate the #218/#221 sequence in a throwaway repository and prove the guard fires —
        both the whole-file and the hunk-level shape — and that a branch that names the file,
        a branch that never touches it, and a branch cut from the moved main all pass.

WHAT IT CANNOT SEE. A reversal of a commit older than the window, and a reversal that was
re-worded on the way back (a line changed as well as restored is a new edit, not a reversal).
Both are named in D133 rather than papered over; the window is the price of a walk that
finishes, and `--window 0` means unbounded for a one-off audit.

Stdlib only, no venv: `python3` in the Makefile, same as `docs-audit` and `checks`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

WINDOW = 60
ESCAPE = "PKMNSCAN_REVERT"

Hunk = Tuple[Tuple[str, ...], Tuple[str, ...]]  # (old lines, new lines), -U0 so no context


# ------------------------------------------------------------------------------ git plumbing


def git(args: Sequence[str], cwd: Optional[str] = None, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def git_status(args: Sequence[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return proc.returncode, proc.stdout, proc.stderr


@dataclass
class Commit:
    sha: str
    parents: List[str]
    subject: str
    # path -> (old blob, new blob), against the FIRST parent. A zero blob is absent.
    files: Dict[str, Tuple[str, str]] = field(default_factory=dict)

    @property
    def short(self) -> str:
        return self.sha[:7]

    @property
    def is_merge(self) -> bool:
        return len(self.parents) > 1

    @property
    def parent(self) -> str:
        return self.parents[0] if self.parents else "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


ZERO = "0" * 40
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def first_parent_log(rev: str, cwd: Optional[str] = None, limit: int = 0) -> List[Commit]:
    """Newest first. Each commit's file list is its diff against its FIRST parent, which for a
    merge is exactly what that merge brought onto the line being walked."""
    args = [
        "log", "--first-parent", "--diff-merges=first-parent", "--raw", "--no-renames",
        "--no-abbrev", "--format=%x01%H %P%x02%s",
    ]
    if limit:
        args.append(f"-n{limit}")
    args.append(rev)
    out = git(args, cwd)
    commits: List[Commit] = []
    cur: Optional[Commit] = None
    for line in out.splitlines():
        if line.startswith("\x01"):
            head, _, subject = line[1:].partition("\x02")
            parts = head.split()
            cur = Commit(sha=parts[0], parents=parts[1:], subject=subject)
            commits.append(cur)
        elif line.startswith(":") and cur is not None:
            meta, _, path = line.partition("\t")
            bits = meta.split()
            # :oldmode newmode oldsha newsha status
            if len(bits) >= 5:
                cur.files[path] = (bits[2], bits[3])
    return commits


_HUNK_CACHE: Dict[Tuple[str, str, str, str], List[Hunk]] = {}
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")


def hunks(old: str, new: str, path: str, cwd: Optional[str] = None) -> List[Hunk]:
    """The -U0 hunks of `git diff old new -- path`, each as (old lines, new lines). Binary and
    whitespace-only hunks are dropped: a reversed blank line is not evidence of anything."""
    key = (cwd or "", old, new, path)
    if key in _HUNK_CACHE:
        return _HUNK_CACHE[key]
    out = git(["diff", "-U0", "--no-color", "--no-renames", old, new, "--", path], cwd)
    result: List[Hunk] = []
    minus: List[str] = []
    plus: List[str] = []

    def flush() -> None:
        if minus or plus:
            if any(s.strip() for s in minus) or any(s.strip() for s in plus):
                result.append((tuple(minus), tuple(plus)))
        minus.clear()
        plus.clear()

    in_hunks = False
    for line in out.splitlines():
        if _HUNK_HEADER.match(line):
            flush()
            in_hunks = True
            continue
        if not in_hunks:
            continue
        if line.startswith("-"):
            minus.append(line[1:])
        elif line.startswith("+"):
            plus.append(line[1:])
        elif line.startswith("\\"):  # "\ No newline at end of file"
            continue
        else:
            flush()
    flush()
    _HUNK_CACHE[key] = result
    return result


def reversed_hunk(h: Hunk) -> Hunk:
    return (h[1], h[0])


# ---------------------------------------------------------------------------- the detection


@dataclass
class Hit:
    path: str
    kind: str                      # "whole-file" or "hunk"
    reverted: Commit               # the earlier first-parent commit whose change was undone
    reversed_hunks: List[Hunk]     # in the reverting diff's direction
    total_hunks: int               # how many hunks the reverting diff had on this file
    via: List[str] = field(default_factory=list)  # commits inside a merged branch that made it

    @property
    def entire(self) -> bool:
        """The whole of what the change does to this file is undo the earlier commit — the
        stale-copy signature."""
        return self.kind == "whole-file" or (self.total_hunks > 0 and len(self.reversed_hunks) == self.total_hunks)


def find_reversals(
    old: str, new: str, files: Dict[str, Tuple[str, str]], earlier: Sequence[Commit],
    cwd: Optional[str] = None,
) -> List[Hit]:
    """`files` is what a change (old -> new) does to each path; `earlier` is the history it
    lands on, newest first, already cut to the window. One Hit per (path, earlier commit)."""
    hits: List[Hit] = []
    for path, (a, b) in sorted(files.items()):
        touched = [e for e in earlier if path in e.files]
        if not touched:
            continue
        mine: Optional[List[Hunk]] = None
        for e in touched:
            ea, eb = e.files[path]
            if eb == a and ea == b and a != b:
                hits.append(Hit(path, "whole-file", e, hunks(old, new, path, cwd),
                                len(hunks(old, new, path, cwd)), via=_via(e, path, cwd)))
                continue
            if mine is None:
                mine = hunks(old, new, path, cwd)
            if not mine:
                break
            theirs = hunks(e.parent, e.sha, path, cwd)
            if not theirs:
                continue
            their_set = set(theirs)
            rev = [h for h in mine if reversed_hunk(h) in their_set]
            if rev:
                hits.append(Hit(path, "hunk", e, rev, len(mine), via=_via(e, path, cwd)))
    return hits


def _via(e: Commit, path: str, cwd: Optional[str]) -> List[str]:
    """For a merge on the first-parent line, the branch commits that actually touched the file —
    the commit a person would name, rather than the merge that carried it."""
    if not e.is_merge:
        return []
    out = git(["log", "--format=%H", f"{e.parents[0]}..{e.sha}", "--", path], cwd)
    return [s for s in out.split() if s != e.sha]


DECISION = re.compile(r"\bD(\d{1,3})\b")


def decisions_in(hs: Iterable[Hunk]) -> List[str]:
    found = set()
    for old, new in hs:
        for line in (*old, *new):
            for m in DECISION.finditer(line):
                found.add(int(m.group(1)))
    return [f"D{n}" for n in sorted(found)]


def message_names(message: str, path: str) -> bool:
    base = os.path.basename(path)
    stem = os.path.splitext(base)[0]
    return path in message or base in message or (len(stem) > 3 and stem in message)


# ---------------------------------------------------------------------------------- gh lookup

_PR_CACHE: Dict[str, Optional[int]] = {}
_MERGE_SUBJECT = re.compile(r"Merge pull request #(\d+)")


def pr_for(c: Commit, use_gh: bool) -> Optional[int]:
    m = _MERGE_SUBJECT.search(c.subject)
    if m:
        return int(m.group(1))
    if not use_gh or shutil.which("gh") is None:
        return None
    if c.sha in _PR_CACHE:
        return _PR_CACHE[c.sha]
    proc = subprocess.run(
        ["gh", "api", f"repos/{{owner}}/{{repo}}/commits/{c.sha}/pulls", "--jq", ".[0].number"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    num = int(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip().isdigit() else None
    _PR_CACHE[c.sha] = num
    return num


# ------------------------------------------------------------------------------- history mode


def full_message(c: Commit, cwd: Optional[str] = None) -> str:
    """The commit's own message — and for a merge, every message on the branch it merged, since
    "Merge pull request #N" names no file and the branch's commits are what a person wrote."""
    text = git(["log", "-1", "--format=%B", c.sha], cwd)
    if c.is_merge:
        text += git(["log", "--format=%B", f"{c.parents[0]}..{c.sha}"], cwd)
    return text


def cmd_history(args: argparse.Namespace) -> int:
    commits = first_parent_log(args.rev)
    if args.since:
        stop = git(["rev-parse", args.since]).strip()
        idx = next((i for i, c in enumerate(commits) if c.sha == stop), len(commits))
        commits = commits[: idx + 1]
    window = args.window
    decisions_now = ""
    try:
        with open("docs/DECISIONS.md", encoding="utf-8") as fh:
            decisions_now = fh.read()
    except OSError:
        pass

    report: List[dict] = []
    total_hits = 0
    for i, c in enumerate(commits):
        earlier = commits[i + 1: i + 1 + window] if window else commits[i + 1:]
        if not earlier or not c.files:
            continue
        hits = find_reversals(c.parent, c.sha, c.files, earlier)
        if not hits:
            continue
        message = full_message(c)
        rows = []
        for h in hits:
            named = message_names(message, h.path)
            if named and not args.all:
                continue
            rows.append({
                "path": h.path, "kind": h.kind, "entire": h.entire,
                "reversed_hunks": len(h.reversed_hunks), "total_hunks": h.total_hunks,
                "reverted": h.reverted.short, "reverted_subject": h.reverted.subject,
                "reverted_pr": pr_for(h.reverted, not args.no_gh),
                "via": [v[:7] for v in h.via],
                "decisions": decisions_in(h.reversed_hunks),
                "named_in_message": named,
                "hunks": [list(map(list, hh)) for hh in h.reversed_hunks] if args.show else None,
            })
        if not rows:
            continue
        total_hits += len(rows)
        report.append({
            "commit": c.short, "subject": c.subject, "merge": c.is_merge,
            "pr": pr_for(c, not args.no_gh),
            "decisions_md_mentions_commit": c.short in decisions_now,
            "files": rows,
        })

    if args.json:
        json.dump({"window": window, "commits": len(commits), "hits": report}, sys.stdout, indent=2)
        print()
        return 0

    print(f"revert audit  first-parent {args.rev}, {len(commits)} commits, window {window or 'unbounded'}")
    print()
    if not report:
        print("  no reversal found.")
        return 0
    for entry in report:
        pr = f"PR #{entry['pr']}" if entry["pr"] else "no PR found"
        print(f"  {entry['commit']}  {pr}  {'merge' if entry['merge'] else 'commit'}")
        print(f"    {entry['subject']}")
        print(f"    DECISIONS.md at HEAD mentions {entry['commit']}: {'yes' if entry['decisions_md_mentions_commit'] else 'NO'}")
        for row in entry["files"]:
            if row["kind"] == "whole-file":
                shape = "whole file restored"
            else:
                shape = f"{row['reversed_hunks']}/{row['total_hunks']} hunks reversed" + (" (entire diff)" if row["entire"] else "")
            rpr = f"PR #{row['reverted_pr']}" if row["reverted_pr"] else "no PR"
            via = f" via {' '.join(row['via'])}" if row["via"] else ""
            named = "named in message" if row["named_in_message"] else "NOT named in message"
            print(f"    - {row['path']}: {shape}; undoes {row['reverted']} ({rpr}{via}); {named}")
            print(f"        {row['reverted_subject']}")
            if row["decisions"]:
                print(f"        cites {', '.join(row['decisions'])}")
            if row["hunks"]:
                for old, new in row["hunks"]:
                    for line in old:
                        print(f"        -{line}")
                    for line in new:
                        print(f"        +{line}")
                    print("        --")
        print()
    print(f"  {total_hits} reversal(s) across {len(report)} commit(s).")
    return 0


# -------------------------------------------------------------------------------- branch mode


def landing(upstream: str, head: str, cwd: Optional[str] = None) -> Tuple[str, str, str]:
    """What merging `head` into `upstream` would change: (old, new, how). `new` is a tree the
    clean merge produced, or `head` itself off the merge-base when the merge conflicts."""
    code, out, _ = git_status(["merge-tree", "--write-tree", upstream, head], cwd)
    if code == 0:
        return upstream, out.split()[0], "clean merge against upstream"
    base = git(["merge-base", upstream, head], cwd).strip()
    return base, head, "the merge conflicts, so the branch's own diff off the merge-base"


def raw_files(old: str, new: str, cwd: Optional[str] = None) -> Dict[str, Tuple[str, str]]:
    out = git(["diff-tree", "-r", "--no-renames", "--no-abbrev", "--raw", old, new], cwd)
    files: Dict[str, Tuple[str, str]] = {}
    for line in out.splitlines():
        if not line.startswith(":"):
            continue
        meta, _, path = line.partition("\t")
        bits = meta.split()
        if len(bits) >= 5:
            files[path] = (bits[2], bits[3])
    return files


def guard(upstream: str, head: str, window: int, cwd: Optional[str] = None, out=sys.stdout) -> int:
    if os.environ.get(ESCAPE, "") == "off":
        print(f"revert guard: {ESCAPE}=off, running nothing.", file=out)
        return 0
    code, _, _ = git_status(["rev-parse", "--verify", "-q", f"{upstream}^{{commit}}"], cwd)
    if code != 0:
        print(f"revert guard: no `{upstream}` here — nothing to compare against, allowing.", file=out)
        return 0
    head_sha = git(["rev-parse", head], cwd).strip()
    up_sha = git(["rev-parse", upstream], cwd).strip()
    if head_sha == up_sha or git_status(["merge-base", "--is-ancestor", head_sha, up_sha], cwd)[0] == 0:
        print(f"revert guard: {head} is at or behind {upstream}; nothing would land.", file=out)
        return 0

    old, new, how = landing(upstream, head_sha, cwd)
    files = raw_files(old, new, cwd)
    if not files:
        print(f"revert guard: {how} changes nothing.", file=out)
        return 0
    earlier = first_parent_log(upstream, cwd, limit=window)
    hits = find_reversals(old, new, files, earlier, cwd)
    base = git(["merge-base", upstream, head_sha], cwd).strip()
    message = git(["log", "--format=%B", f"{base}..{head_sha}"], cwd)

    refused: List[Hit] = []
    declared: List[Hit] = []
    partial: List[Hit] = []
    for h in hits:
        if message_names(message, h.path):
            declared.append(h)
        elif h.entire:
            refused.append(h)
        else:
            partial.append(h)

    print(f"revert guard: {how}; {len(files)} file(s), window {window} commits of {upstream}.", file=out)
    for h in declared:
        print(f"  ok      {h.path} reverses {h.reverted.short}, and a commit on this branch names the file.", file=out)
    for h in partial:
        print(f"  note    {h.path}: {len(h.reversed_hunks)} of {h.total_hunks} hunks reverse "
              f"{h.reverted.short} ({h.reverted.subject}) beside other edits — look at it.", file=out)
    if not refused:
        print(f"  ok      no unexplained reversal.", file=out)
        return 0

    print("", file=out)
    print("REFUSED: this branch carries a stale copy of a file main has moved on.", file=out)
    print("", file=out)
    for h in refused:
        shape = "the whole file restored to its state before" if h.kind == "whole-file" else \
            f"every one of its {h.total_hunks} hunk(s) the exact reverse of"
        print(f"  {h.path}", file=out)
        print(f"    {shape} {h.reverted.short}  {h.reverted.subject}", file=out)
        for v in h.via:
            print(f"    made by {v[:7]} on the branch that merge carried", file=out)
        ds = decisions_in(h.reversed_hunks)
        if ds:
            print(f"    the lines cite {', '.join(ds)}", file=out)
    print("", file=out)
    print("  No commit on this branch names any of these files. This is the shape of a merge", file=out)
    print("  from main resolved by keeping `ours`: the file looks unchanged in your editor and", file=out)
    print("  the diff against main is somebody else's work, backwards. D133 has the account.", file=out)
    print("", file=out)
    print("  If the branch never meant to touch the file:  git checkout " + upstream + " -- <path>", file=out)
    print("  If it means to put the file back:             say so, in a commit message, by file name.", file=out)
    print(f"  Escape hatch, deliberate and loud:            {ESCAPE}=off", file=out)
    print("", file=out)
    return 1


def cmd_branch(args: argparse.Namespace) -> int:
    upstream = args.upstream
    if git_status(["rev-parse", "--verify", "-q", f"{upstream}^{{commit}}"])[0] != 0 and upstream == "origin/main":
        if git_status(["rev-parse", "--verify", "-q", "main^{commit}"])[0] == 0:
            upstream = "main"
    return guard(upstream, args.head, args.window)


# -------------------------------------------------------------------------------- self-test


def cmd_selftest(_: argparse.Namespace) -> int:
    """The #218/#221 sequence, in a repository built and destroyed for the run."""
    passed = 0
    failed = 0

    def ok(what: str) -> None:
        nonlocal passed
        passed += 1
        print(f"  ok     {what}")

    def bad(what: str, detail: str = "") -> None:
        nonlocal failed
        failed += 1
        print(f"  FAIL   {what}")
        if detail:
            for line in detail.rstrip().splitlines():
                print(f"         {line}")

    class Sink:
        def __init__(self) -> None:
            self.text = ""

        def write(self, s: str) -> None:
            self.text += s

        def flush(self) -> None:
            pass

    def run_guard(cwd: str, expect_refusal: bool, what: str, upstream: str = "origin/main") -> None:
        sink = Sink()
        code = guard(upstream, "HEAD", WINDOW, cwd, out=sink)
        if expect_refusal:
            if code != 0 and "REFUSED:" in sink.text:
                ok(f"{what} — refused")
            else:
                bad(f"{what} — expected a refusal, exit {code}", sink.text)
        else:
            if code == 0 and "REFUSED:" not in sink.text:
                ok(what)
            else:
                bad(f"{what} — expected to pass, exit {code}", sink.text)

    print("revert-guard self-test")
    tmp = tempfile.mkdtemp(prefix="pkmnscan-revert.")
    env_backup = os.environ.pop(ESCAPE, None)
    try:
        origin = os.path.join(tmp, "origin.git")
        work = os.path.join(tmp, "work")
        git(["init", "-q", "--bare", origin])
        git(["init", "-q", "-b", "main", work])
        for k, v in (("user.email", "selftest@example.com"), ("user.name", "selftest"),
                     ("commit.gpgsign", "false")):
            git(["config", k, v], work)

        def write(path: str, text: str) -> None:
            full = os.path.join(work, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(text)

        def commit(msg: str, *paths: str) -> str:
            git(["add", "-A", *paths] if paths else ["add", "-A"], work)
            git(["commit", "-q", "-m", msg], work)
            return git(["rev-parse", "HEAD"], work).strip()

        component = "\n".join(f"line {i}" for i in range(1, 21)) + "\nfunction LocationCard() {}\n"
        write("app/Inventory.tsx", component)
        write("app/Other.tsx", "other v1\n")
        # The fixture's decision number is assembled at run time so the map audit does not read
        # a citation of a real entry out of a throwaway file's contents.
        dn = "D" + "1"
        write("docs/DECISIONS.md", f"## {dn} — a ruling\n\nThe card stays.\n")
        commit("the store as it stood")
        git(["remote", "add", "origin", origin], work)
        git(["push", "-q", "-u", "origin", "main"], work)

        # ---- PR #218: a branch deletes LocationCard and amends the decision, then merges.
        git(["checkout", "-q", "-b", "deletion"], work)
        write("app/Inventory.tsx", "\n".join(f"line {i}" for i in range(1, 21)) + "\n")
        write("docs/DECISIONS.md", f"## {dn} — a ruling\n\nThe card is deleted ({dn}).\n")
        deletion = commit(f"{dn}: delete LocationCard")
        git(["checkout", "-q", "main"], work)
        git(["merge", "-q", "--no-ff", "-m", "Merge pull request #218 from x/deletion", "deletion"], work)
        merge218 = git(["rev-parse", "HEAD"], work).strip()
        git(["push", "-q", "origin", "main"], work)

        # ---- PR #221: cut BEFORE the deletion, merges main keeping ours, squashes on top.
        git(["checkout", "-q", "-b", "cap-wording", f"{merge218}^1"], work)
        write("app/Other.tsx", "other v2 — the cap is a ceiling\n")
        commit("The cap is a ceiling on copies live")
        # merge main keeping OURS for everything — the resolution that carried the revert
        git(["merge", "-q", "-s", "ours", "--no-edit", "main"], work)
        # squash onto main as one commit whose message says nothing about Inventory.tsx
        tree = git(["rev-parse", "HEAD^{tree}"], work).strip()
        squashed = git(["commit-tree", tree, "-p", merge218, "-m", "The cap is a ceiling on copies live"], work).strip()
        git(["checkout", "-q", "-B", "cap-wording", squashed], work)

        # The fixture asserts its own arming: the squash really does carry the old blob.
        old_blob = git(["rev-parse", f"{merge218}^1:app/Inventory.tsx"], work).strip()
        now_blob = git(["rev-parse", "HEAD:app/Inventory.tsx"], work).strip()
        if old_blob == now_blob and old_blob != git(["rev-parse", f"{merge218}:app/Inventory.tsx"], work).strip():
            ok("fixture armed: the squashed branch carries the pre-deletion Inventory.tsx")
        else:
            bad("fixture not armed — the squash did not carry the old blob")

        run_guard(work, True, "the #221 shape: a squashed keep-ours merge restoring a deleted component")

        # ---- The history walk sees the same thing once it lands.
        git(["checkout", "-q", "main"], work)
        git(["merge", "-q", "--ff-only", "cap-wording"], work)
        git(["push", "-q", "origin", "main"], work)
        commits = first_parent_log("main", work)
        hits = find_reversals(commits[0].parent, commits[0].sha, commits[0].files, commits[1:], work)
        whole = [h for h in hits if h.kind == "whole-file" and h.path == "app/Inventory.tsx"]
        if whole and whole[0].reverted.sha == merge218 and deletion in whole[0].via:
            ok("history: the landed commit is a whole-file reversal of the #218 merge, via the deleting commit")
        else:
            bad("history: the whole-file reversal was not found", repr([(h.path, h.kind, h.reverted.short) for h in hits]))
        if any(h.path == "docs/DECISIONS.md" and dn in decisions_in(h.reversed_hunks) for h in hits):
            ok(f"history: the reverted decision text cites {dn}")
        else:
            bad(f"history: {dn} not read out of the reverted hunks")

        # ---- Re-apply the deletion on main (as D119 was), then the branch cases below.
        git(["checkout", "-q", "main"], work)
        write("app/Inventory.tsx", "\n".join(f"line {i}" for i in range(1, 21)) + "\n")
        write("docs/DECISIONS.md", f"## {dn} — a ruling\n\nThe card is deleted ({dn}), again.\n")
        reapplied = commit(f"{dn} re-applied")
        git(["push", "-q", "origin", "main"], work)

        # A clean branch off the moved main, editing something else, passes.
        git(["checkout", "-q", "-b", "clean", "main"], work)
        write("app/Other.tsx", "other v3\n")
        commit("Other moves on")
        run_guard(work, False, "a branch off the moved main that never touches the file")

        # A branch that reverses ONE hunk among real edits is a note, not a refusal.
        git(["checkout", "-q", "-b", "partial", "main"], work)
        write("app/Inventory.tsx", "function Another() {}\n" + component)
        commit("Another component lands")
        sink = Sink()
        code = guard("origin/main", "HEAD", WINDOW, work, out=sink)
        if code == 0 and "note" in sink.text and "1 of 2 hunks" in sink.text:
            ok("a partial reversal beside real edits is reported as a note and allowed")
        else:
            bad("partial reversal handling", sink.text)

        # A branch that restores the file AND says so by name passes.
        git(["checkout", "-q", "-b", "declared", "main"], work)
        write("app/Inventory.tsx", component)
        commit("Bring LocationCard back in app/Inventory.tsx, on the owner's word")
        run_guard(work, False, "a declared restoration — the commit message names the file")

        # The same restoration with a message that names nothing is refused, and at HUNK level:
        # main adds a comment to the file first and the branch keeps it, so the restored blob
        # matches no blob main ever held and only the reversed hunk can see it.
        git(["checkout", "-q", "main"], work)
        commented = "\n".join(f"line {i}" for i in range(1, 21)) + "\n// a comment main added\n"
        write("app/Inventory.tsx", commented)
        commit("main adds a comment")
        git(["push", "-q", "origin", "main"], work)
        git(["checkout", "-q", "-b", "silent", "main"], work)
        write("app/Inventory.tsx", commented + "function LocationCard() {}\n")
        commit("Wording")
        run_guard(work, True, "a silent restoration after main moved the file — the hunk-level shape")

        # The escape hatch runs nothing and says so.
        os.environ[ESCAPE] = "off"
        sink = Sink()
        code = guard("origin/main", "HEAD", WINDOW, work, out=sink)
        del os.environ[ESCAPE]
        if code == 0 and f"{ESCAPE}=off" in sink.text:
            ok("the escape hatch is honoured and named")
        else:
            bad("escape hatch", sink.text)

        # A branch at upstream's tip has nothing to land.
        git(["checkout", "-q", "main"], work)
        run_guard(work, False, "main itself: nothing would land")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if env_backup is not None:
            os.environ[ESCAPE] = env_backup

    print()
    print(f"  {passed} passed, {failed} failed")
    return 1 if failed else 0


# ---------------------------------------------------------------------------------------- main


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)

    h = sub.add_parser("history", help="walk first-parent main and report every reversal")
    h.add_argument("rev", nargs="?", default="main")
    h.add_argument("--window", type=int, default=WINDOW, help="earlier commits to compare against (0: all)")
    h.add_argument("--since", help="stop the walk at this commit (inclusive)")
    h.add_argument("--all", action="store_true", help="include hits the commit's message names")
    h.add_argument("--show", action="store_true", help="print the reversed hunks")
    h.add_argument("--no-gh", action="store_true", help="skip the PR lookup for non-merge commits")
    h.add_argument("--json", action="store_true")
    h.set_defaults(func=cmd_history)

    b = sub.add_parser("branch", help="the guard: refuse an unexplained reversal on the way to upstream")
    b.add_argument("--upstream", default="origin/main")
    b.add_argument("--head", default="HEAD")
    b.add_argument("--window", type=int, default=WINDOW)
    b.set_defaults(func=cmd_branch)

    s = sub.add_parser("selftest", help="the #218/#221 sequence in a throwaway repository")
    s.set_defaults(func=cmd_selftest)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
