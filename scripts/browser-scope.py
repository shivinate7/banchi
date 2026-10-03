#!/usr/bin/env python3
"""DOES THIS CHANGE REACH WHAT A BROWSER DRAWS? (D141)

`.github/workflows/check.yml`'s `design-check` job is three shards of roughly nine minutes
each, so one push costs about 27 billed runner-minutes, and until D141 it ran on every push
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
        measurement in D141 was taken and how it is re-taken.
    scripts/browser-scope.py specs [--base REV] [--head REV]
        THE SECOND LEVER (D215). Once the matrix is going to RUN, which
        `app/tests/*.spec.ts` files can the change actually reach? Writes
        `specs=<space-separated paths|all>` and `partial=true|false` to GITHUB_OUTPUT, and a
        one-line summary to GITHUB_STEP_SUMMARY when that is set. NEVER a typed list: for
        each spec, its own relative import closure, plus the closure of every screen whose
        route hash the spec's body names (comments stripped first, matched against
        `app/src/App.tsx`'s own `ROUTES`), plus every screen when the spec sweeps
        the nav (calls `routesFromNav(` itself or through a test-side helper it imports). A shared surface (`app/src/kit/**`, `tokens.css`, `base.css`,
        `App.tsx`, `main.tsx`, `index.html`, `app/public/**`, a
        config or package file, or anything already in the top-level `SCOPE` outside
        `app/**`) selects every spec. So does an unmapped `app/**` path, an empty or
        unreadable diff, no merge-base, a path carrying whitespace (`PW_ARGS` is word-split
        by `make`), or `PKMNSCAN_BROWSER_SCOPE=all` — printed by name on every such skip.
        A non-spec `app/tests/*` file selects the specs whose import closure holds it; one no spec imports selects every spec.
        `partial=true` only when the run is genuinely narrowed, so `design-check-passed`
        never records a tree as fully tested on a partial run.
    scripts/browser-scope.py shard N M [SPEC ...]
        THE THIRD LEVER. Which spec files run on shard N of M, packed by measured TIME, not
        case count: Playwright's own `--shard` left one shard near 513 s and another near
        306 s. SPEC ... narrows the universe (the `specs` output); none means every spec.
        Whole files, slowest first, onto the lightest shard, from `scripts/browser-spec-
        times.json` (file name to seconds: each test's median over 50 `check.yml` runs).
        A spec with no time gets the mean, so a stale table costs balance, never coverage.
    scripts/browser-scope.py shard-refresh FILE ... [--write]
        Re-time from `.serve/design-check.json` files (`fileSeconds`). The nightly uploads
        each shard's as `design-check-times-N`; download them and run this. Previews.
    scripts/browser-scope.py list
    scripts/browser-scope.py selftest

Stdlib only, and `git` — it runs on a bare runner before anything is installed (D18).
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Set

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
        "path": "scripts/port-slots.py",
        "why": "Named in the `design-check` recipe: it claims this checkout's port slot "
               "before the suite starts, so it decides which port the browser is pointed at "
               "(D261).",
    },
    {
        "path": "scripts/reap_mark.py",
        "why": "Named in the `design-check` recipe: it stamps the suite's own process with "
               "this session's id before `suite-lock.py` starts it (D305). "
               "A bug here does not change what the browser draws, but it runs before the "
               "suite does, on the same recipe line, so a change to it changes what runs.",
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
    {
        "path": "scripts/kit-adoption.mjs",
        "why": "Read by `app/tests/scaffold.spec.ts`, which runs it with `--routes` to get "
               "the route table it sweeps (D275). A change to how it reads "
               "`ROUTES` changes which routes the browser measures.",
    },
    {
        "path": "scripts/kit-adoption-allow.json",
        "why": "Read by `app/tests/scaffold.spec.ts`: its `runtime` block is the shrinking "
               "offender list the spec reconciles against (D275). Deleting an "
               "entry is a claim that a screen now passes, and only the browser proves it.",
    },
    {
        "path": "scripts/machine-words.json",
        "why": "Read by `app/tests/text-checks.spec.ts`: the one word list the rendered-text "
               "check scans every route for (D196, D284). A word added or "
               "removed changes what the browser refuses, so only the browser proves it. The "
               "three browser pending lists (`app/tests/*-allow.json`) sit under `app/**` "
               "already. `scripts/machine-words-allow.json` is the AST row's list and no spec "
               "reads it.",
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


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or [ast.Pass()]
    return tree


def ast_equal(before: Optional[str], after: Optional[str]) -> bool:
    """True only when both sides parse and have the same AST with docstrings stripped, so a
    comment or docstring edit is equal. Equal AST is equal behavior, unless the source reads its
    own `__doc__` (then the docstring is behavior and is kept). A parse error, a missing side
    or any exception is False: fail open."""
    if before is None or after is None:
        return False
    try:
        keep = "__doc__" in before or "__doc__" in after
        dump = [ast.dump(t if keep else _strip_docstrings(t))
                for t in (ast.parse(before), ast.parse(after))]
        return dump[0] == dump[1]
    except Exception:  # noqa: BLE001
        return False


def _header(source: str) -> tuple:
    """A module's docstring and its top-level UPPERCASE names: what a reader of the module's
    prose and section list sees."""
    tree = ast.parse(source)
    names = [t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets
             if isinstance(t, ast.Name) and t.id.isupper()]
    return ast.get_docstring(tree), names


def header_equal(before: Optional[str], after: Optional[str]) -> bool:
    if before is None or after is None:
        return False
    try:
        return _header(before) == _header(after)
    except Exception:  # noqa: BLE001
        return False


def skippable_on_ast(sources: Sequence[Path]) -> Callable[[str], bool]:
    """The `ast_skip` predicate for a gate whose test sources are `sources`: a file the test
    NAMES (its path or its file name appears in any of them) is never skipped on equal AST,
    because a test that names a file may patch it by exact text, and a quote swap or a comment
    then breaks its anchor while the AST is unchanged. An unreadable source: nothing skips."""
    try:
        text = "\n".join(Path(q).read_text(encoding="utf-8", errors="replace") for q in sources)
    except OSError:
        return lambda path: False
    return lambda path: path not in text and Path(path).name not in text


def classify_paths(paths: Sequence[str], read_side: SideReader,
                   scope: Sequence[dict] = SCOPE, subject: str = "what a browser draws",
                   noun: str = "the matrix",
                   ast_skip: Optional[Callable[[str], bool]] = None) -> Verdict:
    """The pure half: a list of changed paths in, a verdict out. No git, no environment.

    `scope`, `subject` and `noun` are parameters because a SECOND gate now asks the same
    question about a different suite (`scripts/serve-scope.py`, 2026-09-17). They default to
    this file's own, so every existing caller is unchanged, and the alternative was a second
    copy of the globbing and the recipe narrowing — the two pieces here that are subtle
    enough to drift apart without anyone noticing which copy was right.
    """
    lines: List[str] = []
    run = False
    if not paths:
        return Verdict(True, [
            "no changed files were found. That is more likely a wrong base than an empty "
            f"change, so {noun} RUNS."])
    for path in paths:
        hits = [entry for entry in scope if matches(entry["path"], path)]
        if not hits:
            lines.append(f"  skip  {path}")
            continue
        entry = hits[0]
        within = entry.get("within")
        if (
            within is None
            and ast_skip is not None
            and path.endswith(".py")
            and ast_skip(path)
            and ast_equal(read_side("base", path), read_side("head", path))
        ):
            lines.append(f"  skip  {path}  (comment or docstring change only: same AST)")
            continue
        if within in ("exists", "header"):
            before, after = read_side("base", path), read_side("head", path)
            if within == "exists":
                same = (before is None) == (after is None)
                what = "only whether it exists is read, and that is unchanged"
            else:
                same = before == after or header_equal(before, after)
                what = "only its docstring and section names are read, and they are unchanged"
            lines.append(f"  skip  {path}  ({what})" if same else
                         f"  RUN   {path}  ({'created or deleted' if within == 'exists' else 'docstring or section names changed'})")
            run = run or not same
            continue
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
        f"the change reaches {subject} — {noun} RUNS" if run
        else f"nothing here reaches {subject} — {noun} is SKIPPED")
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
    """The verdict for main's last `count` first-parent commits — the D141 measurement."""
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
    # HERMETIC: a hatch inherited from the environment (CI sets it on every push to main)
    # would make this self-test's own SKIP cases run. Its cases set the hatch themselves.
    os.environ.pop("PKMNSCAN_BROWSER_SCOPE", None)
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
    ok(not classify_paths(["harness/traces/motion-trace-x.json"], read_side).run,
       "a trace skips now that no spec reads one — the cadence spec that did is deleted, and "
       "the entry went with it rather than staying as an unjustified widening")
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

    print("\nimport resolution, over the real tree")
    # THE AMBIGUOUS SPECIFIER: `app/src/kit/` is a directory AND `app/src/kit.css` is a
    # stylesheet beside it, so `from './kit'` is exactly the shape a fixed extension order
    # decides wrongly. The bundler's answer is the directory's entry file. Both halves of
    # the precondition are asserted, so this case can never pass by the files being absent.
    ok((ROOT / "app/src/kit/index.tsx").is_file() and (ROOT / "app/src/kit.css").is_file(),
       "the ambiguous pair exists: `app/src/kit/index.tsx` beside `app/src/kit.css`")
    ok(resolve_relative("app/src/Inventory.tsx", "./kit") == "app/src/kit/index.tsx",
       "a bare `./kit` resolves to the directory's entry file, not the stylesheet beside it")
    ok(resolve_relative("app/src/Inventory.tsx", "./kit.css") == "app/src/kit.css",
       "`./kit.css`, named in full, still resolves to the stylesheet")
    ok("app/src/kit/index.tsx" in import_closure(["app/src/Inventory.tsx"]),
       "so the kit's own components are inside a screen's import closure")

    print("\nthe spec map (D215), over the real tree")
    inventory_verdict = classify_specs(["app/src/Inventory.tsx"])
    ok("app/tests/inventory.spec.ts" in inventory_verdict.specs,
       "`app/src/Inventory.tsx` reaches `inventory.spec.ts`")
    ok("app/tests/cursor.spec.ts" in inventory_verdict.specs,
       "`app/src/Inventory.tsx` reaches a `routesFromNav(` spec (`cursor.spec.ts`)")
    ok("app/tests/text-checks.spec.ts" in inventory_verdict.specs,
       "`app/src/Inventory.tsx` reaches the specs that sweep through `sweepEveryRoute`, "
       "a helper that calls `routesFromNav(` for them")
    ok(not _NAV_CALL_RE.search("export async function routesFromNav(page: Page)"),
       "the `routesFromNav` definition is not a call")
    ok("app/tests/review.spec.ts" not in inventory_verdict.specs,
       "`app/src/Inventory.tsx` does not reach `review.spec.ts`")
    ok(inventory_verdict.partial, "a real screen file narrows the run")

    # THE BARE `#/` CASE: home is the one route whose hash has no letters after the slash,
    # and a hash regex written for `#/inventory`-shaped paths misses it by construction —
    # `_ROUTE_HASH_RE` must accept the empty tail too, or Home's own spec is invisible to
    # its own screen forever.
    home_verdict = classify_specs(["app/src/Home.tsx"])
    ok("app/tests/home.spec.ts" in home_verdict.specs,
       "`app/src/Home.tsx` reaches `home.spec.ts` — a bare `#/` names the `/` route")

    # THE OTHER DIRECTION: every route in `ROUTES` must be named by an explicit spec body,
    # not left to a `routesFromNav(` sweep alone — a sweep asserts something generic about
    # whatever screen is current, never a claim that IT tested this one. A route that fails
    # this is `unnamed_route_views()`'s job to catch and `is_shared_surface`'s job to protect.
    unnamed = unnamed_route_views()
    if unnamed:
        print(f"  (unnamed, so shared: {', '.join(sorted(unnamed))})")
    ok(all(is_shared_surface(view) for view in unnamed),
       "every unnamed route's view file is protected as a shared surface")
    ok(is_shared_surface("app/src/Home.tsx") or "app/src/Home.tsx" not in unnamed,
       "Home is named by its own spec today, so it is not swept-only")

    kit_verdict = classify_specs(["app/src/kit/Icon.tsx"])
    ok(kit_verdict.specs == set(all_specs()) and not kit_verdict.partial,
       "a path under `app/src/kit/` selects every spec")

    unknown_verdict = classify_specs(["app/src/NoSuchScreenEver.tsx"])
    ok(unknown_verdict.specs == set(all_specs()) and not unknown_verdict.partial,
       "an unknown `app/` path selects every spec — an unmapped file is a gap, not a skip")

    space_verdict = classify_specs(["app/src/My File.tsx"])
    ok(space_verdict.specs == set(all_specs()) and not space_verdict.partial,
       "a path carrying whitespace selects every spec")

    # THAT ALONE IS NOT PROOF THE WHITESPACE CLAUSE FIRED — `app/src/My File.tsx` is also
    # unmapped, so the unmapped-path fallback reaches the same answer with the clause
    # deleted. Map the space path to exactly one spec via `classify_specs`'s own `reverse`
    # injection and check the whitespace clause still overrides that mapping — the
    # whitespace check runs BEFORE the reverse-map lookup, so a real mapping proves the
    # clause and not the fallback.
    mapped_path = "app/src/My File.tsx"
    fake_reverse = {mapped_path: {"app/tests/home.spec.ts"}}
    mapped_space_verdict = classify_specs([mapped_path], reverse=fake_reverse)
    ok(mapped_space_verdict.specs == set(all_specs()) and not mapped_space_verdict.partial,
       "a whitespace path MAPPED to one spec still selects every spec — the clause, not "
       "the unmapped fallback, is what fires")

    old = os.environ.get("PKMNSCAN_BROWSER_SCOPE")
    os.environ["PKMNSCAN_BROWSER_SCOPE"] = "all"
    try:
        off_verdict = classify_specs(["app/src/Inventory.tsx"])
    finally:
        if old is None:
            os.environ.pop("PKMNSCAN_BROWSER_SCOPE", None)
        else:
            os.environ["PKMNSCAN_BROWSER_SCOPE"] = old
    ok(off_verdict.specs == set(all_specs()) and not off_verdict.partial,
       "PKMNSCAN_BROWSER_SCOPE=all selects every spec")

    # A TEST HELPER SELECTS ONLY THE SPECS THAT IMPORT IT (D215, amended); one nothing imports
    # selects all. `moneyFace.ts` is the control: reached by the text-checks spec, not by all.
    helper = classify_specs(["app/tests/moneyFace.ts"])
    ok(helper.partial and "app/tests/text-checks.spec.ts" in helper.specs
       and len(helper.specs) < len(all_specs()),
       "a test helper selects only the specs whose closure holds it")
    unread = classify_specs(["app/tests/no-spec-imports-this.ts"])
    ok(unread.specs == set(all_specs()) and not unread.partial,
       "a test file no spec imports selects every spec (fail open)")

    # THE COMMENT-ONLY ARM AND THE TWO NARROWINGS, each through the pure classifier.
    py_scope = ({"path": "x/**", "why": "x"},)
    pair = lambda a, b: (lambda side, path: a if side == "base" else b)  # noqa: E731
    skip_all = lambda path: True  # noqa: E731
    base_src = '"""doc."""\nx = 1  # c\n'
    verdict_for = lambda a, b: classify_paths(  # noqa: E731
        ["x/m.py"], pair(a, b), scope=py_scope, ast_skip=skip_all).run
    ok(not verdict_for(base_src, '"""other doc."""\nx = 1\n'),
       "a docstring and comment edit skips")
    ok(verdict_for(base_src, '"""doc."""\nx = 2\n'), "a code edit runs")
    ok(verdict_for(base_src, "def (:\n"), "a parse error runs")
    ok(verdict_for('"""d"""\nprint(__doc__)\n', '"""e"""\nprint(__doc__)\n'),
       "a docstring the module reads as `__doc__` runs")
    ok(classify_paths(["x/m.py"], pair(base_src, base_src + "#\n"), scope=py_scope).run,
       "without ast_skip a comment edit still runs (opt-in only)")
    exists_scope = ({"path": "x/f", "within": "exists", "why": "x"},)
    ok(not classify_paths(["x/f"], pair("a", "b"), scope=exists_scope).run,
       "an existence-only subject skips a content edit")
    ok(classify_paths(["x/f"], pair(None, "b"), scope=exists_scope).run,
       "an existence-only subject runs when the file is created")
    ok(classify_paths(["x/f"], pair("a", None), scope=exists_scope).run,
       "an existence-only subject runs when the file is deleted")
    header_scope = ({"path": "x/m.py", "within": "header", "why": "x"},)
    ok(not classify_paths(["x/m.py"], pair(base_src, base_src.replace("x = 1", "y = 2")),
                          scope=header_scope).run, "a header subject skips a body edit")
    ok(classify_paths(["x/m.py"], pair(base_src, base_src.replace("doc.", "new.")),
                      scope=header_scope).run, "a header subject runs on a docstring edit")
    ok(classify_paths(["x/m.py"], pair(base_src, base_src + "TRACKS = 1\n"),
                      scope=header_scope).run, "a header subject runs on a new section name")

    shard_selftest_cases(ok)

    print()
    if failures:
        print(f"{len(failures)} failed")
        return 1
    print("clean")
    return 0


# --------------------------------------------------------------------------- the spec map
#
# THE SECOND LEVER (D215). Once `classify` above has decided the matrix
# RUNS, this answers a narrower question: which `app/tests/*.spec.ts` files can the change
# actually reach? DERIVED, never typed, on the same argument SCOPE makes for itself: a
# filter too narrow silently stops testing something, so every direction this cannot resolve
# answers "every spec" rather than a guess.


class SpecVerdict(NamedTuple):
    specs: Set[str]
    partial: bool
    lines: List[str]


APP_SRC = "app/src"
APP_TESTS = "app/tests"

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")


def strip_comments(text: str) -> str:
    """`/* */` first, then `//` to end of line. A `//` inside a string or URL is stripped
    along with it, but that only ever REMOVES a hash mention this reads — it cannot manufacture
    one — so this direction never opens a gap; a literal `'/#/review'` in real code survives."""
    return _LINE_COMMENT_RE.sub("", _BLOCK_COMMENT_RE.sub("", text))


_IMPORT_RE = re.compile(
    r"""(?:import|export)\s+(?:type\s+)?(?:[\w*${},\s]+\s+from\s+)?['"](\.[^'"]+)['"]""")
_CSS_IMPORT_RE = re.compile(r"""@import\s+['"](\.[^'"]+)['"]""")
# THE ORDER IS THE BUNDLER'S, NOT A CONVENIENT ONE. A module specifier carries no
# extension, so what it names is decided by the order these are tried, and the first hit
# wins. Vite resolves a JS/TS specifier by extension and then by the directory's own entry
# file; `.css` is not in its extension list at all — a stylesheet is imported by its full
# name. So `from './kit'` names `app/src/kit/index.tsx`, NEVER `app/src/kit.css`, and a
# list that tried `.css` before `/index.tsx` answered with the stylesheet wherever a
# directory and a same-named stylesheet both exist. `.css` stays on the JS list, LAST, as
# a fail-open tail rather than a resolution rule: this reader's whole discipline is that a
# miss silently narrows what gets tested, so an edge it cannot name properly is still
# better followed than dropped. A CSS `@import` is a different grammar and gets its own
# list, where `.css` is what the specifier means.
_JS_EXTENSIONS = (
    "", ".tsx", ".ts", ".jsx", ".js",
    "/index.tsx", "/index.ts", "/index.jsx", "/index.js",
    ".css",
)
_CSS_EXTENSIONS = ("", ".css", "/index.css")


def resolve_relative(from_path: str, module: str, css: bool = False) -> Optional[str]:
    """A relative import (`./Foo`, `../kit`) resolved to a tracked repo-relative path.
    `css` says the specifier came from a CSS `@import`, which resolves by its own rules."""
    base = (ROOT / from_path).parent
    for ext in (_CSS_EXTENSIONS if css else _JS_EXTENSIONS):
        candidate = (base / (module + ext)).resolve()
        try:
            candidate_rel = candidate.relative_to(ROOT).as_posix()
        except ValueError:
            continue
        if candidate.is_file():
            return candidate_rel
    return None


def file_imports(path: str) -> List[str]:
    """Every relative import in one tracked file (JS/TS `from`, side-effect `import '...'`,
    CSS `@import`), resolved. A bare package import (`react`, `@playwright/test`) is ignored:
    it never leads back into `app/**`."""
    full = ROOT / path
    if not full.is_file():
        return []
    try:
        text = strip_comments(full.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return []
    found = [(module, False) for module in _IMPORT_RE.findall(text)]
    if path.endswith(".css"):
        found += [(module, True) for module in _CSS_IMPORT_RE.findall(text)]
    out: List[str] = []
    for module, css in found:
        resolved = resolve_relative(path, module, css=css)
        if resolved is not None:
            out.append(resolved)
    return out


def import_closure(start: Sequence[str]) -> Set[str]:
    """Every file `start` reaches by relative import, transitively, `start` itself included."""
    seen: Set[str] = set()
    queue = list(start)
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        queue.extend(file_imports(path))
    return seen


_ROUTE_RE = re.compile(r"path:\s*'([^']+)'.*?view:\s*(\w+)")
_ROUTE_IMPORT_RE = re.compile(r"import\s*\{\s*([^}]+?)\s*\}\s*from\s*'(\.[^']+)'")


def route_views(app_tsx: str = "app/src/App.tsx") -> Dict[str, str]:
    """`ROUTES` read out of `app/src/App.tsx` itself, as `{route path: view's repo file}` —
    the same table `make orient` reads one screen at a time, read here for all of them."""
    full = ROOT / app_tsx
    if not full.is_file():
        return {}
    text = full.read_text(encoding="utf-8", errors="replace")
    names: Dict[str, str] = {}
    for group, module in _ROUTE_IMPORT_RE.findall(text):
        resolved = resolve_relative(app_tsx, module)
        if resolved is None:
            continue
        for name in (n.strip().split()[-1] for n in group.split(",") if n.strip()):
            names[name] = resolved
    out: Dict[str, str] = {}
    for route_path, view in _ROUTE_RE.findall(text):
        if view in names:
            out[route_path] = names[view]
    return out


_ROUTE_HASH_RE = re.compile(r"#(/[a-z][a-z0-9-]*|/)")


def spec_named_views(spec_path: str, routes: Dict[str, str]) -> Set[str]:
    """The view files a spec names EXPLICITLY, by route hash in its own (comment-stripped)
    body — never through a nav sweep (`sweeps_nav`). Shared between `spec_reach` (which adds
    the sweep's own routes on top) and `unnamed_route_views` (which asks whether a screen is
    ever named this way by ANYONE, or only ever swept)."""
    full = ROOT / spec_path
    text = full.read_text(encoding="utf-8", errors="replace") if full.is_file() else ""
    stripped = strip_comments(text)
    named: Set[str] = set()
    for hash_path in sorted(set(_ROUTE_HASH_RE.findall(stripped))):
        view = routes.get(hash_path)
        if view is not None:
            named.add(view)
    return named


_NAV_CALL_RE = re.compile(r"(?<!function )routesFromNav\(")


def sweeps_nav(spec_path: str) -> bool:
    """Does this spec visit whatever the nav draws? True when its own (comment-stripped) body
    calls `routesFromNav(`, OR when any test-side module it imports, transitively, does — a
    helper such as `routeSweep.ts:sweepEveryRoute` makes the call for the spec, and reading
    only the spec's own text missed `text-checks.spec.ts`. The
    definition (`function routesFromNav(`) is not a call. Fails open: a spec that imports a
    sweeping helper for an unrelated export is still counted as sweeping."""
    for path in import_closure([spec_path]):
        if not path.startswith(APP_TESTS + "/"):
            continue
        full = ROOT / path
        text = full.read_text(encoding="utf-8", errors="replace") if full.is_file() else ""
        if _NAV_CALL_RE.search(strip_comments(text)):
            return True
    return False


def spec_reach(spec_path: str, routes: Dict[str, str]) -> Set[str]:
    """One spec's own footprint: its own import closure, plus the closure of every screen
    whose route hash its (comment-stripped) body names, plus every screen when it sweeps the
    nav (`sweeps_nav`) — a sweep that visits whatever the nav currently draws."""
    starts = [spec_path]
    if sweeps_nav(spec_path):
        starts.extend(routes.values())
    else:
        starts.extend(spec_named_views(spec_path, routes))
    return import_closure(starts)


_unnamed_routes_cache: Optional[Set[str]] = None


def unnamed_route_views() -> Set[str]:
    """Route view files reached only by a `routesFromNav(` sweep, never named by hash in any
    spec's own body. A sweep asserts something generic about whatever screen is current; it
    is not a substitute for a spec that actually claims to be testing that screen. A route
    that fails this is treated as a shared surface — fail open — rather than trusted to the
    sweep alone. Cached at module scope, same reasoning as `shell_closure`."""
    global _unnamed_routes_cache
    if _unnamed_routes_cache is not None:
        return _unnamed_routes_cache
    routes = route_views()
    named: Set[str] = set()
    for spec in all_specs():
        if sweeps_nav(spec):
            continue
        named |= spec_named_views(spec, routes)
    _unnamed_routes_cache = set(routes.values()) - named
    return _unnamed_routes_cache


def all_specs() -> List[str]:
    tests_dir = ROOT / APP_TESTS
    if not tests_dir.is_dir():
        return []
    return sorted(f"{APP_TESTS}/{p.name}" for p in tests_dir.iterdir()
                 if p.name.endswith(".spec.ts"))


_SHARED_PREFIXES = ("app/src/kit/", "app/public/")
_SHARED_EXACT = {
    "app/src/tokens.css", "app/src/base.css", "app/src/App.tsx", "app/src/App.css",
    "app/src/main.tsx", "app/index.html",
}
_SHARED_APP_FILES = {
    "app/playwright.config.ts", "app/vite.config.ts", "app/devPort.ts",
    "app/checkoutIdentity.ts", "app/design-check-reporter.ts", "app/eslint.config.js",
}


_shell_closure_cache: Optional[Set[str]] = None


def shell_closure() -> Set[str]:
    """`App.tsx` and `main.tsx`'s own support files, CUT OFF AT THE SCREEN BOUNDARY: a BFS
    from the shell's two files that never expands past a route's own view file, so a
    screen's private imports are never swept in, but everything the shell needs to run at
    all — `deviceMemory.ts`, `keys.ts`, `server.ts`, `usePoll.ts`, the kit, the tokens — is.
    Cached at module scope: this reads the tree once, and every caller in one process asks
    the same question of the same commit."""
    global _shell_closure_cache
    if _shell_closure_cache is not None:
        return _shell_closure_cache
    view_files = set(route_views().values())
    seen: Set[str] = set()
    queue = ["app/src/App.tsx", "app/src/main.tsx"]
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        if path in view_files:
            continue
        queue.extend(file_imports(path))
    _shell_closure_cache = seen - view_files
    return _shell_closure_cache


def is_shared_surface(path: str) -> bool:
    """A path that selects every spec on its own: the shell's own closure (`App.tsx`,
    `main.tsx` and everything they need that is not a screen's own view file), the kit, the
    tokens, a non-spec test helper or fixture, and the config/package files `app/**` carries
    beside the screens (Playwright, Vite, tsconfig, package files, the lint config that rides
    along in D141's own SCOPE entry)."""
    if any(path.startswith(prefix) for prefix in _SHARED_PREFIXES):
        return True
    if path in _SHARED_EXACT or path in _SHARED_APP_FILES:
        return True
    if path in shell_closure():
        return True
    if path in unnamed_route_views():
        return True
    # A non-spec test file is NOT shared: `build_reverse_map` maps it to the specs whose import
    # closure holds it, and one no spec imports (read at run time) is unmapped, which selects
    # every spec (fail open).
    return path.startswith("app/") and (
        path.endswith(("package.json", "package-lock.json")) or
        re.search(r"tsconfig[^/]*\.json$", path) is not None
    )


def build_reverse_map() -> Dict[str, Set[str]]:
    """Every tracked file's reachers: the specs whose own `spec_reach` closure covers it."""
    routes = route_views()
    reverse: Dict[str, Set[str]] = {}
    for spec in all_specs():
        for path in spec_reach(spec, routes):
            reverse.setdefault(path, set()).add(spec)
    return reverse


def classify_specs(paths: Sequence[str],
                   reverse: Optional[Dict[str, Set[str]]] = None) -> SpecVerdict:
    """Which specs `paths` can reach, or every spec, and whether that is a genuine narrowing.

    NEVER A BLOCK-LIST: every direction this cannot resolve — an unmapped `app/**` path, a
    shared surface, a path outside `app/**` that is already top-level SCOPE, a path with
    whitespace (`PW_ARGS` is word-split by `make`), an empty diff, or the escape hatch —
    answers "every spec", printed by name.

    `reverse` is dependency injection, for the selftest ONLY: it lets a case substitute a
    fake reverse map (a whitespace path mapped to one real spec) without reassigning the
    module-level `build_reverse_map` name, which a static checker reads as a redefinition
    when the substitution happens above the real `def` in this file.
    """
    everyone = set(all_specs())
    if os.environ.get("PKMNSCAN_BROWSER_SCOPE") == "all":
        return SpecVerdict(everyone, False,
                           ["PKMNSCAN_BROWSER_SCOPE=all — every spec runs."])
    if not paths:
        return SpecVerdict(everyone, False, [
            "no changed files were found. That is more likely a wrong base than an empty "
            "change, so every spec runs."])
    if reverse is None:
        reverse = build_reverse_map()
    lines: List[str] = []
    result: Set[str] = set()
    narrowed_any = False
    forced_all = False
    for path in paths:
        if re.search(r"\s", path):
            lines.append(f"  ALL   {path}  (whitespace in a path cannot be named to "
                         "PW_ARGS, which `make` word-splits)")
            forced_all = True
            continue
        if not path.startswith("app/"):
            # NO `within: recipe:design-check` NARROWING HERE, deliberately, unlike
            # `classify_paths` above. That narrowing needs BOTH sides of the diff (the
            # recipe's text before and after), and `classify_specs` only ever receives a
            # list of paths — no `read_side`. Threading one through would let a Makefile
            # change outside the recipe (e.g. `make up`) narrow the SPEC list even while
            # `classify` still correctly answers RUN for the same change (SCOPE's own
            # `within` narrowing can still SKIP the matrix on `run`). Reusing that same
            # narrowing here would make `run` and `specs` agree in effect, but at the cost
            # of a second, unproven code path for the rarer case (a Makefile touch inside a
            # branch whose matrix already runs). A Makefile touch forcing every spec is the
            # safe direction — SCOPE's own entries are few and rarely touched — so this is
            # left over-inclusive on purpose rather than partially threaded.
            hit = next((entry for entry in SCOPE if matches(entry["path"], path)), None)
            if hit is not None:
                lines.append(f"  ALL   {path}  (outside `app/**`, already in the top-level "
                             f"SCOPE — {hit['path']})")
                forced_all = True
            else:
                lines.append(f"  --    {path}  (outside `app/**`, not in SCOPE either — no "
                             "spec's concern)")
            continue
        if is_shared_surface(path):
            lines.append(f"  ALL   {path}  (a shared surface)")
            forced_all = True
            continue
        reachers = reverse.get(path)
        if not reachers:
            lines.append(f"  ALL   {path}  (no spec's derived closure reaches it — an "
                         "unmapped file is a gap in the map, never a license to skip it)")
            forced_all = True
            continue
        narrowed_any = True
        result |= reachers
        lines.append(f"  {len(reachers)} spec(s)  {path}")
    if forced_all or not narrowed_any:
        lines.append("every spec runs")
        return SpecVerdict(everyone, False, lines)
    partial = result != everyone
    lines.append(f"{len(result)} of {len(everyone)} spec(s) reached" +
                 (" — a genuine narrowing" if partial else " — every spec, derived rather "
                  "than forced"))
    return SpecVerdict(result, partial, lines)


def write_spec_output(verdict: SpecVerdict) -> None:
    text = "all" if verdict.specs == set(all_specs()) and not verdict.partial \
        else " ".join(sorted(verdict.specs))
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(f"specs={text}\n")
            handle.write(f"partial={'true' if verdict.partial else 'false'}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            if verdict.partial:
                handle.write(f"partial: {len(verdict.specs)} of {len(all_specs())} specs\n")
            else:
                handle.write("partial: false — every spec runs\n")


def classify_specs_revisions(base: str, head: str) -> SpecVerdict:
    start = landing_base(base, head)
    if start is None:
        return SpecVerdict(set(all_specs()), False,
                           [f"no merge-base between {base} and {head} — every spec runs."])
    paths = changed_paths(start, head)
    if paths is None:
        return SpecVerdict(set(all_specs()), False,
                           [f"`git diff {start[:12]} {head}` failed — every spec runs."])
    verdict = classify_specs(paths)
    return SpecVerdict(verdict.specs, verdict.partial,
                       [f"{len(paths)} changed path(s) from {start[:12]} to {head}:"]
                       + verdict.lines)


# ----------------------------------------------------------------------------------- main


# --------------------------------------------------------------------------- the shards
#
# THE THIRD LEVER. `check.yml` runs the browser matrix as M shards; this says which spec
# files each one runs. Longest-processing-time packing over measured seconds per file.

SPEC_TIMES = ROOT / "scripts" / "browser-spec-times.json"


def spec_cost(specs: Sequence[str], times: Dict[str, float]) -> Dict[str, float]:
    """Seconds per spec. A spec with no measured time is given the MEDIAN of those that have
    one, so a new spec is packed and never refused. The nightly `shard-refresh --write`
    replaces the default with a measured time."""
    known = sorted(times[Path(s).name] for s in specs if Path(s).name in times)
    median = known[len(known) // 2] if known else 1.0
    return {s: times.get(Path(s).name, median) for s in specs}


def stale_times(specs: Sequence[str], times: Dict[str, float]) -> List[str]:
    """Timed names that no spec file carries. The file cannot rot in this direction."""
    names = {Path(s).name for s in specs}
    return sorted(n for n in times if n not in names)


def pack_shards(specs: Sequence[str], shards: int, times: Dict[str, float]):
    """`[[load, [spec, ...]], ...]`: each spec, slowest first (ties by name), onto the
    lightest shard. Costs come from `spec_cost`."""
    cost = spec_cost(specs, times)
    bins: List[list] = [[0.0, []] for _ in range(shards)]
    for spec in sorted(specs, key=lambda s: (-cost[s], s)):
        lightest = min(bins, key=lambda b: b[0])
        lightest[0] += cost[spec]
        lightest[1].append(spec)
    return bins


def load_spec_times() -> Dict[str, float]:
    return json.loads(SPEC_TIMES.read_text(encoding="utf-8"))


def shard_refresh(files: Sequence[str], write: bool) -> int:
    total: Dict[str, float] = {}
    for f in files:
        for name, secs in json.loads(Path(f).read_text(encoding="utf-8")).get(
                "fileSeconds", {}).items():
            total[name] = total.get(name, 0.0) + secs
    if not total:
        print("no `fileSeconds` in those files; refusing to write an empty table")
        return 1
    table = {k: round(v, 1) for k, v in sorted(total.items())}
    if write:
        SPEC_TIMES.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
    print(f"{len(table)} specs, {sum(table.values()):.0f}s total; "
          f"{'written' if write else 'preview, --write saves'}")
    return 0


def shard_selftest_cases(ok: Callable[[bool, str], None]) -> None:
    print("\nthe shards, by time")
    times, specs = load_spec_times(), all_specs()
    defaulted = [s for s in specs if Path(s).name not in times]
    print(f"  {len(defaulted)} of {len(specs)} specs are timed by the median default, not measured")
    ok(True, "every spec has a time, measured or defaulted")
    ok(stale_times(specs, times) == [], "no timed entry names a spec that no longer exists")
    ok(stale_times(specs, {**times, "gone.spec.ts": 5.0}) == ["gone.spec.ts"],
       "a stale timed entry is caught")
    fresh = specs + ["app/tests/brand-new.spec.ts"]
    ok(stale_times(fresh, times) == stale_times(specs, times)
       and spec_cost(fresh, times)["app/tests/brand-new.spec.ts"]
       == sorted(times[Path(s).name] for s in specs if Path(s).name in times)[
           len([s for s in specs if Path(s).name in times]) // 2],
       "a new untimed spec passes and costs the median")
    ok(any("app/tests/brand-new.spec.ts" in b[1] for b in pack_shards(fresh, 6, times)),
       "a new untimed spec lands on a shard")
    for m in (6, 3):
        bins = pack_shards(specs, m, times)
        ok(sorted(s for _, files in bins for s in files) == specs,
           f"{m} shards hold every spec exactly once")
        loads = [b[0] for b in bins]
        # A whole spec is indivisible, so the best possible slowest shard is the mean
        # or the largest spec, whichever is bigger.
        floor = max(sum(loads) / m, max(spec_cost(specs, times).values()))
        ok(max(loads) <= floor * 1.1,
           f"{m} shards: slowest {max(loads):.0f}s within 10% of the best possible {floor:.0f}s")
    ok([b[1] for b in pack_shards(specs, 6, times)]
       == [b[1] for b in pack_shards(list(reversed(specs)), 6, times)],
       "the split does not depend on input order")
    ok(sum(len(b[1]) for b in pack_shards(specs[:2], 6, times)) == 2,
       "fewer specs than shards loses none")
    ok(sum(len(b[1]) for b in pack_shards(specs + ["app/tests/new.spec.ts"], 6, times))
       == len(specs) + 1, "a spec with no time is still assigned")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    classify = sub.add_parser("classify", help="the workflow's question, answered")
    classify.add_argument("--base", help="a revision; the merge-base against --head is the start")
    classify.add_argument("--head", default="HEAD")
    classify.add_argument("--event", default=os.environ.get("GITHUB_EVENT_NAME", "pull_request"))
    hist = sub.add_parser("history", help="the verdict over main's last N first-parent commits")
    hist.add_argument("count", nargs="?", type=int, default=20)
    specs = sub.add_parser("specs", help="which app/tests/*.spec.ts files the change reaches")
    specs.add_argument("--base", help="a revision; the merge-base against --head is the start")
    specs.add_argument("--head", default="HEAD")
    sh = sub.add_parser("shard", help="spec files for shard N of M, packed by time")
    sh.add_argument("n", type=int)
    sh.add_argument("m", type=int)
    sh.add_argument("specs", nargs="*")
    refresh = sub.add_parser("shard-refresh", help="re-time from design-check.json files")
    refresh.add_argument("files", nargs="+")
    refresh.add_argument("--write", action="store_true")
    sub.add_parser("list", help="the scope, with each entry's reason")
    sub.add_parser("selftest", help="prove the matcher and the narrowing")
    args = parser.parse_args(argv)

    if args.command == "list":
        for entry in SCOPE:
            within = f"  (within {entry['within']})" if entry.get("within") else ""
            print(f"{entry['path']}{within}\n    {entry['why']}\n")
        return 0
    if args.command == "shard":
        if not 1 <= args.n <= args.m:
            print(f"shard {args.n} is outside 1..{args.m}", file=sys.stderr)
            return 2
        bins = pack_shards(args.specs or all_specs(), args.m, load_spec_times())
        print(" ".join(sorted(bins[args.n - 1][1])))
        return 0
    if args.command == "shard-refresh":
        return shard_refresh(args.files, args.write)
    if args.command == "history":
        return history(args.count)
    if args.command == "selftest":
        return selftest()
    if args.command == "specs":
        unnamed = unnamed_route_views()
        if unnamed:
            print("route naming — named by a sweep only, never by an explicit spec, so "
                 "treated as shared:")
            for view in sorted(unnamed):
                print(f"  {view}")
        base = args.base
        if base is None:
            base_ref = os.environ.get("GITHUB_BASE_REF", "")
            base = f"origin/{base_ref}" if base_ref else None
        if base is None:
            spec_verdict = SpecVerdict(set(all_specs()), False,
                                       ["no base to diff against — every spec runs."])
        else:
            spec_verdict = classify_specs_revisions(base, args.head)
        for line in spec_verdict.lines:
            print(line)
        write_spec_output(spec_verdict)
        return 0

    verdict = classify_event(args.event, args.base, args.head)
    for line in verdict.lines:
        print(line)
    write_output(verdict.run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
