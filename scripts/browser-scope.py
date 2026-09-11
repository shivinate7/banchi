#!/usr/bin/env python3
"""DOES THIS CHANGE REACH WHAT A BROWSER DRAWS? (D-ci-browser-scope)

`.github/workflows/check.yml`'s `design-check` job is three shards of roughly nine minutes
each, so one push costs about 27 billed runner-minutes, and until D-ci-browser-scope it ran on every push
to every branch. Measured 2026-09-11: seven pull requests plus re-runs landed in one evening
and most touched no screen code at all — a docs auditor (#260), a key-rotation fix (#261), a
harness test (#267), a supervisor guard (#262). Each paid the full browser cost, three times
over, to prove that stylesheets it never opened still render, and the account ran out of
Actions minutes. The browser matrix caught one real thing all night, on a screen change.

D136's gate cannot answer this. It skips the post-merge run on main when the exact TREE has
already passed on the PR, and a docs-only branch is always a new tree. This is the
complement: on a pull request, run the matrix only when what the branch LANDS touches a file
the suite reads. The two gates act on different events and never on the same one.

THE LIST IS DERIVED, NOT TYPED, AND IT HAS A READER. `SCOPE` below names every path the
suite depends on, each with the reason it is there, worked out from what `make design-check`
actually loads — Vite's root, Playwright's `testDir`, the trace a spec reads off disk, the
recipe that starts it, and the gate's own two files. `make docs-audit`'s `browser scope` row
reconciles it against those sources in both directions and fails a commit when they drift,
because a path filter that is too narrow silently stops testing something, and a gate that
quietly stops running is worse than no gate: the green is believed. That sentence is
`scripts/githooks/pre-commit`'s, about its own armed copy — the same failure one level up.

WHAT IS DELIBERATELY NOT IN THE LIST: `server/`. `app/tests/shell.ts:sealEveryTest` registers
a catch-all `page.route` on this checkout's capture port, ABORTS every request to it, and
asserts in `afterEach` that none was attempted — so the suite cannot observe a server change
by construction, and running it on one proves nothing a docs change would not. The
`spec seal` audit row is what keeps that true; the day a spec forwards a request to the real
server, `server/` becomes a dependency and both that row and this list have to move. A route
change is caught where it can be seen: harness T7 in `make check`, and `app/src/types.ts`,
which is the wire's only client-side declaration and is inside `app/**`.

IT FAILS OPEN, IN EVERY DIRECTION IT CAN. An unknown event, a base it cannot find, a diff it
cannot compute, an EMPTY diff (more likely a wrong base than an empty change), and a recipe
it cannot extract on either side all answer RUN, out loud. `check.yml` reads the answer as
`!= 'false'`, so a job that never ran answers RUN too. Only an explicit `false` skips.

AND IT NEVER ACTS ON A PUSH TO MAIN. There the diff is classified and PRINTED so the
mechanism is exercised on every run rather than watched once a week, and the answer is RUN
regardless — D136's pass record is the only thing that skips the matrix on main.

    scripts/browser-scope.py classify [--base REV] [--head REV] [--event NAME]
        The workflow's call. With no flags it reads GITHUB_EVENT_NAME and GITHUB_BASE_REF and
        writes `run=true|false` to GITHUB_OUTPUT. Locally: `--base origin/main` classifies
        what this branch would land.
    scripts/browser-scope.py history [N]
        The verdict for each of main's last N first-parent commits, which is how the
        measurement in D-ci-browser-scope was taken and how it is re-taken.
    scripts/browser-scope.py list
    scripts/browser-scope.py selftest

Stdlib only, and `git` — it runs on a bare runner before anything is installed (D18).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent

RUN = "run"
SKIP = "skip"

# EVERY PATH THE BROWSER SUITE READS, AND WHY. Pure literals: `scripts/docs-audit.py` reads
# this tuple with `ast.literal_eval` rather than importing the module, and reconciles it
# against the sources each `why` names. A `within` narrows a path to the part of it the suite
# reads — `recipe:<target>` is the Makefile recipe of that name plus the variables it expands,
# compared as text between the two sides of the diff — because the Makefile is touched by
# every third merge and the browser reads four lines of it.
SCOPE = (
    {
        "path": "app/**",
        "why": "Vite's root. `app/vite.config.ts` sets no `root`, so the dev server the suite "
               "runs against serves `app/index.html`, `app/src/`, `app/public/` and reads its "
               "own config, `tsconfig.json` and the package files from here; `server.fs.allow` "
               "defaults to this directory, so nothing outside it can be served at all. "
               "Playwright's `testDir` is `app/tests/`, its config imports `app/devPort.ts` "
               "and its reporter is `app/design-check-reporter.ts`. The one tracked file under "
               "here neither tool reads is `app/eslint.config.js`, and it rides along on the "
               "side of running.",
    },
    {
        "path": "harness/traces/**",
        "why": "`app/tests/cadence.spec.ts` reads two recordings of the rig off disk with "
               "`readFileSync` and replays the cadence trigger over them. A trace is a suite "
               "input the browser never fetches, which is exactly what a hand-typed list of "
               "`app/` paths misses.",
    },
    {
        "path": "Makefile",
        "within": "recipe:design-check",
        "why": "The job runs `make design-check`, and this is the recipe. Narrowed to the "
               "recipe and the variables it expands: a change to `make up` is not a change to "
               "what the browser sees.",
    },
    {
        "path": "scripts/suite-lock.py",
        "why": "Named in the `design-check` recipe: the suite starts through it.",
    },
    {
        "path": ".github/workflows/check.yml",
        "why": "The gate itself. A change to how the matrix is invoked, sharded or skipped "
               "has to run the matrix, or the change is verified by nothing.",
    },
    {
        "path": "scripts/browser-scope.py",
        "why": "The classifier. Same argument as the workflow: a change to the gate's own "
               "reasoning is proven only by the run it decides about.",
    },
)


class Verdict(NamedTuple):
    run: bool
    lines: List[str]  # one per changed path, plus the sentences that decided


# ------------------------------------------------------------------------------ matching


def glob_re(pattern: str) -> "re.Pattern[str]":
    """GitHub Actions' path-filter globbing, which is also gitignore's: `**` crosses `/`,
    `*` and `?` do not. A bare path is itself."""
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            if i < len(pattern) and pattern[i] == "/":
                # `a/**/b` also matches `a/b`: the separator is part of the wildcard.
                out[-1] = "(?:.*/)?"
                i += 1
            continue
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(pattern: str, path: str) -> bool:
    return glob_re(pattern).match(path) is not None


# ------------------------------------------------------------------- the recipe narrowing

_RECIPE_VAR_RE = re.compile(r"\$\((\w+)\)")


def recipe_text(makefile: str, target: str) -> Optional[str]:
    """One Makefile recipe as the text the browser suite actually depends on, or None.

    The recipe lines of `<target>:` plus the definition of every `$(VAR)` they expand, one
    level deep — enough for `$(NPM_GUARD)`, `$(ARGS)` and `$(PW_ARGS)`, which is all the
    recipe uses. Comments above the rule are not included: prose about the recipe is not the
    recipe. None when the rule is not there, which the caller treats as RUN.
    """
    lines = makefile.split("\n")
    head = re.compile(r"^" + re.escape(target) + r"\s*:")
    body: List[str] = []
    for index, line in enumerate(lines):
        if not head.match(line):
            continue
        for following in lines[index + 1:]:
            if following.startswith("\t"):
                body.append(following)
            elif following.strip() == "" or following.startswith("#"):
                continue
            else:
                break
        break
    if not body:
        return None
    names = sorted({name for line in body for name in _RECIPE_VAR_RE.findall(line)})
    definitions: List[str] = []
    for name in names:
        define = re.compile(r"^" + re.escape(name) + r"\s*[:?+]?=")
        for index, line in enumerate(lines):
            if not define.match(line):
                continue
            definitions.append(line)
            # A `\`-continued definition runs on until a line without the backslash.
            cursor = index
            while lines[cursor].rstrip().endswith("\\") and cursor + 1 < len(lines):
                cursor += 1
                definitions.append(lines[cursor])
            break
    return "\n".join(body + definitions)


# ------------------------------------------------------------------------- classification

# Reads one side of the diff: `read_side("base", "Makefile")` is that file's content at the
# base revision, or None when it does not exist there.
SideReader = Callable[[str, str], Optional[str]]


def classify_paths(paths: Sequence[str], read_side: SideReader) -> Verdict:
    """The pure half: a list of changed paths in, a verdict out. No git, no environment."""
    lines: List[str] = []
    run = False
    if not paths:
        return Verdict(True, [
            "no changed files were found. That is more likely a wrong base than an empty "
            "change, so the matrix RUNS."])
    for path in paths:
        hits = [entry for entry in SCOPE if matches(entry["path"], path)]
        if not hits:
            lines.append(f"  skip  {path}")
            continue
        entry = hits[0]
        within = entry.get("within")
        if within is None:
            run = True
            lines.append(f"  RUN   {path}  ({entry['path']})")
            continue
        kind, _, target = str(within).partition(":")
        if kind != "recipe":
            run = True
            lines.append(f"  RUN   {path}  (`within` {within!r} is not a narrowing this "
                         f"script knows, so the whole file counts)")
            continue
        before = read_side("base", path)
        after = read_side("head", path)
        recipe_before = recipe_text(before, target) if before is not None else None
        recipe_after = recipe_text(after, target) if after is not None else None
        if recipe_before is None or recipe_after is None:
            run = True
            lines.append(f"  RUN   {path}  (the `{target}` recipe could not be read on "
                         f"{'the base' if recipe_before is None else 'the head'}; "
                         f"an unreadable recipe counts as a changed one)")
        elif recipe_before != recipe_after:
            run = True
            lines.append(f"  RUN   {path}  (the `{target}` recipe changed)")
        else:
            lines.append(f"  skip  {path}  (changed outside the `{target}` recipe)")
    lines.append(
        "the change reaches what a browser draws — the matrix RUNS" if run
        else "nothing here reaches what a browser draws — the matrix is SKIPPED")
    return Verdict(run, lines)


# ------------------------------------------------------------------------------------ git


def git(*args: str) -> Optional[str]:
    done = subprocess.run(
        ["git", *args], cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        check=False,
    )
    if done.returncode != 0:
        return None
    return done.stdout.decode("utf-8", errors="replace")


def changed_paths(base: str, head: str) -> Optional[List[str]]:
    """Every path that differs between two revisions, both sides of a rename included."""
    out = git("diff", "--name-only", "--no-renames", "-z", base, head)
    if out is None:
        return None
    return sorted(entry for entry in out.split("\0") if entry)


def git_reader(base: str, head: str) -> SideReader:
    revisions = {"base": base, "head": head}

    def read_side(side: str, path: str) -> Optional[str]:
        return git("show", f"{revisions[side]}:{path}")

    return read_side


def landing_base(base: str, head: str) -> Optional[str]:
    """Where the change starts: the merge-base, so a branch is judged by what it LANDS.

    On a pull request `HEAD` is GitHub's merge of the branch into its base, whose first
    parent is the base tip at the time; the merge-base against `origin/<base>` is that same
    commit even when the base has moved since. Locally it is the fork point.
    """
    out = git("merge-base", base, head)
    return out.strip() if out else None


def classify_revisions(base: str, head: str) -> Verdict:
    start = landing_base(base, head)
    if start is None:
        return Verdict(True, [f"no merge-base between {base} and {head} — the matrix RUNS."])
    paths = changed_paths(start, head)
    if paths is None:
        return Verdict(True, [f"`git diff {start[:12]} {head}` failed — the matrix RUNS."])
    verdict = classify_paths(paths, git_reader(start, head))
    return Verdict(verdict.run, [f"{len(paths)} changed path(s) from {start[:12]} to {head}:"]
                   + verdict.lines)


# ---------------------------------------------------------------------------- the events


def push_before() -> Optional[str]:
    """The `before` sha of a push event, read off the payload; None when there is none."""
    payload = os.environ.get("GITHUB_EVENT_PATH")
    if not payload:
        return None
    try:
        with open(payload, encoding="utf-8") as handle:
            before = json.load(handle).get("before")
    except (OSError, ValueError):
        return None
    if not before or set(before) == {"0"}:
        return None
    return str(before)


def classify_event(event: str, base: Optional[str], head: str) -> Verdict:
    """What the workflow asks. Acted on for `pull_request`; printed and overruled elsewhere."""
    if base is not None:
        return classify_revisions(base, head)
    if event == "pull_request":
        base_ref = os.environ.get("GITHUB_BASE_REF", "")
        if not base_ref:
            return Verdict(True, ["pull_request with no GITHUB_BASE_REF — the matrix RUNS."])
        return classify_revisions(f"origin/{base_ref}", head)
    if event == "push":
        before = push_before()
        lines = ["push: the matrix runs regardless — D136's pass record is the only thing "
                 "that skips it here. What the scope WOULD have said, so the mechanism is "
                 "exercised on every run:"]
        if before is None:
            lines.append("  (no `before` sha on this push, nothing to classify)")
        else:
            paths = changed_paths(before, head)
            if paths is None:
                lines.append(f"  (`git diff {before[:12]} {head}` failed)")
            else:
                lines.extend(classify_paths(paths, git_reader(before, head)).lines)
        return Verdict(True, lines)
    return Verdict(True, [f"event {event!r} is not one this gate decides — the matrix RUNS."])


def write_output(run: bool) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(f"run={'true' if run else 'false'}\n")


# ------------------------------------------------------------------------------- history


def history(count: int) -> int:
    """The verdict for main's last `count` first-parent commits — the D-ci-browser-scope measurement."""
    out = git("log", "--first-parent", "--format=%H %s", f"-{count}", "main")
    if out is None:
        out = git("log", "--first-parent", "--format=%H %s", f"-{count}")
    if not out:
        print("no history to read")
        return 1
    runs = skips = 0
    for line in out.splitlines():
        sha, _, subject = line.partition(" ")
        paths = changed_paths(f"{sha}^1", sha)
        if paths is None:
            print(f"  ????  {sha[:8]}  {subject[:64]}  (no first parent)")
            continue
        verdict = classify_paths(paths, git_reader(f"{sha}^1", sha))
        runs += verdict.run
        skips += not verdict.run
        reasons = [line.strip() for line in verdict.lines if line.strip().startswith("RUN")]
        why = f"  ← {reasons[0][6:]}" if reasons else ""
        print(f"  {'RUN ' if verdict.run else 'skip'}  {sha[:8]}  {subject[:64]}{why}")
    print(f"\n{runs} would run the browser matrix, {skips} would skip it, of {runs + skips}")
    return 0


# ------------------------------------------------------------------------------ selftest


def selftest() -> int:
    failures: List[str] = []

    def ok(condition: bool, label: str) -> None:
        print(f"  {'ok  ' if condition else 'FAIL'} {label}")
        if not condition:
            failures.append(label)

    fixture: Dict[str, Dict[str, str]] = {"base": {}, "head": {}}

    def read_side(side: str, path: str) -> Optional[str]:
        return fixture[side].get(path)

    print("browser-scope self-test\n" + "=" * 72)
    print("\nglobbing")
    ok(matches("app/**", "app/src/App.tsx"), "`app/**` reaches a nested file")
    ok(matches("app/**", "app/index.html"), "`app/**` reaches a file at the root")
    ok(not matches("app/**", "apple/x"), "`app/**` does not match a prefix of a name")
    ok(matches("Makefile", "Makefile") and not matches("Makefile", "app/Makefile"),
       "a bare path is itself and nothing else")
    ok(not matches("harness/*.json", "harness/traces/x.json"), "`*` stops at `/`")

    print("\nclassifying")
    ok(not classify_paths(["docs/DECISIONS.md", "README.md"], read_side).run,
       "a docs-only change skips")
    ok(classify_paths(["docs/DECISIONS.md", "app/src/App.tsx"], read_side).run,
       "one screen file among docs runs")
    ok(classify_paths(["harness/traces/motion-trace-x.json"], read_side).run,
       "a trace the cadence spec reads runs")
    ok(not classify_paths(["server/capture_server.py", "scripts/serve.py"], read_side).run,
       "a server change skips: the suite seals the capture port")
    ok(classify_paths([], read_side).run, "an empty diff runs, because it is probably a wrong base")
    ok(classify_paths([".github/workflows/check.yml"], read_side).run, "the gate's own file runs")

    print("\nthe recipe narrowing")
    same = "NPM_GUARD = @true\n\nup:\n\t@echo up\n\ndesign-check:\n\t$(NPM_GUARD)\n\t@run it\n"
    fixture["base"]["Makefile"] = same
    fixture["head"]["Makefile"] = same.replace("@echo up", "@echo UP")
    ok(not classify_paths(["Makefile"], read_side).run,
       "a Makefile change outside the recipe skips")
    fixture["head"]["Makefile"] = same.replace("@run it", "@run it --shard")
    ok(classify_paths(["Makefile"], read_side).run, "a change inside the recipe runs")
    fixture["head"]["Makefile"] = same.replace("@true", "@false")
    ok(classify_paths(["Makefile"], read_side).run,
       "a change to a variable the recipe expands runs")
    fixture["head"]["Makefile"] = same.replace("design-check:", "browser-check:")
    ok(classify_paths(["Makefile"], read_side).run,
       "a recipe that cannot be found on one side runs")
    fixture["head"]["Makefile"] = same.replace("\t@run it", "\t@run it # now with a comment")
    ok(classify_paths(["Makefile"], read_side).run,
       "a recipe line's own text is compared verbatim, comments included")

    print("\nthe real Makefile")
    real = (ROOT / "Makefile").read_text(encoding="utf-8") if (ROOT / "Makefile").exists() else ""
    recipe = recipe_text(real, "design-check")
    ok(recipe is not None and "suite-lock.py" in recipe,
       "the `design-check` recipe is found and starts through the lock")
    ok(recipe is not None and "NPM_GUARD" in recipe and "app/node_modules" in recipe,
       "`$(NPM_GUARD)` is expanded one level into the text compared")

    print()
    if failures:
        print(f"{len(failures)} failed")
        return 1
    print("clean")
    return 0


# ----------------------------------------------------------------------------------- main


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    classify = sub.add_parser("classify", help="the workflow's question, answered")
    classify.add_argument("--base", help="a revision; the merge-base against --head is the start")
    classify.add_argument("--head", default="HEAD")
    classify.add_argument("--event", default=os.environ.get("GITHUB_EVENT_NAME", "pull_request"))
    hist = sub.add_parser("history", help="the verdict over main's last N first-parent commits")
    hist.add_argument("count", nargs="?", type=int, default=20)
    sub.add_parser("list", help="the scope, with each entry's reason")
    sub.add_parser("selftest", help="prove the matcher and the narrowing")
    args = parser.parse_args(argv)

    if args.command == "list":
        for entry in SCOPE:
            within = f"  (within {entry['within']})" if entry.get("within") else ""
            print(f"{entry['path']}{within}\n    {entry['why']}\n")
        return 0
    if args.command == "history":
        return history(args.count)
    if args.command == "selftest":
        return selftest()

    verdict = classify_event(args.event, args.base, args.head)
    for line in verdict.lines:
        print(line)
    write_output(verdict.run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
