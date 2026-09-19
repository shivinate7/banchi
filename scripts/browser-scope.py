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
    scripts/browser-scope.py list
    scripts/browser-scope.py specs [--base REV] [--head REV]
        The narrower question, asked only once `classify` has already answered RUN: WHICH
        spec files does a partial run need? Writes `specs=<paths or "all">` and
        `partial=true|false` to GITHUB_OUTPUT. Never widens what `classify` already decided —
        see the header above the `specs_for_changed_paths` function.
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


def classify_paths(paths: Sequence[str], read_side: SideReader,
                   scope: Sequence[dict] = SCOPE, subject: str = "what a browser draws",
                   noun: str = "the matrix") -> Verdict:
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


# --------------------------------------------------------------------------- spec allow-list
#
# `classify` answers ONE question — does the matrix run at all? `specs` answers a narrower
# one, asked only once the matrix is already going to run: WHICH spec files does it need to
# load? Owner's ruling, 2026-09-19: raise the worker count (the real lever, `check.yml`'s
# matrix) AND build this — a derived spec→file map over the last 30 PRs narrows 6 of 30,
# median saving 0, so it is the secondary lever, never the reason to skip the primary one.
#
# THE MAP IS DERIVED FROM THE CHECKED-OUT TREE, NEVER TYPED, THE SAME ARGUMENT `SCOPE` MAKES
# ABOVE ONE LEVEL UP. For each `app/tests/*.spec.ts`: its own relative import closure (`.ts`,
# `.tsx`, `.css`, and a `.css` file's own `@import`s) union the closure of every screen whose
# route hash the spec body names (comments stripped first, `#/xxx` matched against `ROUTES` in
# `app/src/App.tsx`, read the same way — `import { Name } from './File'` beside `path: '/xxx',
# ... view: Name` on one line), and a spec that calls `routesFromNav(` gets EVERY screen's
# closure, because it already sweeps every route the nav renders.
#
# SHARED SURFACES SELECT EVERY SPEC: `App.tsx`'s own closure with the screen imports cut off
# (so `main.tsx` -> `App.tsx` does not silently pull every screen back in), `main.tsx`'s own
# closure with `App.tsx` cut off for the same reason, everything under `app/src/kit/`,
# `tokens.css`, `base.css`, `index.html`, everything under `app/public/`, every
# `app/tests/*` file that is not itself a spec (`.ts` helpers and `.json` fixtures),
# `playwright.config.ts`, `devPort.ts`, `design-check-reporter.ts`, the package files, the
# tsconfigs, and — outside `app/**` — anything already in `SCOPE` above (`check.yml`, this
# file, `suite-lock.py`, the `design-check` Makefile recipe, narrowed the same way `classify`
# narrows it).
#
# IT FAILS OPEN, IN EVERY DIRECTION THE HEADER ABOVE ALREADY ARGUES FOR `classify`: no
# merge-base, an unreadable diff, an EMPTY diff, a changed path under `app/**` that no spec's
# derived closure reaches (an unmapped file is a gap in the map, never a license to skip it),
# a changed path outside `app/**` that IS in `SCOPE`, and a changed path carrying whitespace
# (`PW_ARGS` is word-split by `make`, so a path with a space cannot be named to it at all) —
# every one of these answers "every spec", same as `classify` answers RUN. NEVER a
# block-list: docs/debts records what a guessed one let through once already.
# `PKMNSCAN_BROWSER_SCOPE=off` selects every spec too, and says so by name — the same escape
# hatch `classify`'s caller in `check.yml` already prints.

SELECT_ALL = "all"

_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_IMPORT_FROM_RE = re.compile(
    r"import\s+(?:type\s+)?[^;'\"]*?from\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
_BARE_IMPORT_RE = re.compile(r"(?<!from )import\s*['\"]([^'\"]+)['\"]")
_CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\(\s*)?['\"]?([^'\"()\s;]+)['\"]?\)?")
_NAMED_IMPORT_RE = re.compile(r"import\s*\{\s*(\w+)\s*\}\s*from\s*['\"](\.[^'\"]+)['\"]")
_ROUTE_ROW_RE = re.compile(r"path:\s*'([^']*)'[^\n]*?view:\s*(\w+)")
_HASH_RE = re.compile(r"#(/[a-z-]*)")

_SOURCE_EXTS = (".tsx", ".ts", ".css", ".jsx", ".js")


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(" ", text)


def resolve_relative_import(from_file: Path, spec: str) -> Optional[Path]:
    """A relative import spec, resolved to a file on disk, or None.

    Non-relative specs (`react`, `@playwright/test`, an alias) resolve to None on purpose —
    this map is only ever about files this checkout can change."""
    if not spec.startswith("."):
        return None
    target = (from_file.parent / spec)
    guesses: List[Path] = []
    if target.suffix:
        guesses.append(target)
    else:
        guesses.extend(Path(str(target) + ext) for ext in _SOURCE_EXTS)
        guesses.extend(target / f"index{ext}" for ext in (".tsx", ".ts"))
    for guess in guesses:
        if guess.is_file():
            return guess.resolve()
    return None


def file_imports(path: Path) -> List[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    text = strip_comments(text)
    specs = [m.group(1) for m in _IMPORT_FROM_RE.finditer(text)]
    specs += [m.group(1) for m in _BARE_IMPORT_RE.finditer(text)]
    if path.suffix == ".css":
        specs += [m.group(1) for m in _CSS_IMPORT_RE.finditer(text)]
    return specs


def import_closure(entry: Path, exclude: frozenset = frozenset()) -> set:
    """Every file `entry` reaches through relative imports, `entry` included.

    `exclude` is skipped entirely — neither counted nor recursed into — which is how a
    shared-surface closure is cut off at a screen boundary without walking the whole app."""
    seen: set = set()
    stack = [entry.resolve()]
    while stack:
        current = stack.pop()
        if current in seen or current in exclude or not current.is_file():
            continue
        seen.add(current)
        for spec in file_imports(current):
            resolved = resolve_relative_import(current, spec)
            if resolved is not None and resolved not in seen and resolved not in exclude:
                stack.append(resolved)
    return seen


def route_map(app_dir: Path) -> Dict[str, Path]:
    """`{hash path: screen file}`, read off `app/src/App.tsx`'s own `ROUTES` table and the
    imports beside it — the same table `app/tests/routes.ts` derives its roster from."""
    app_tsx = app_dir / "src" / "App.tsx"
    if not app_tsx.is_file():
        return {}
    text = strip_comments(app_tsx.read_text(encoding="utf-8"))
    component_file: Dict[str, Path] = {}
    for match in _NAMED_IMPORT_RE.finditer(text):
        name, spec = match.group(1), match.group(2)
        resolved = resolve_relative_import(app_tsx, spec)
        if resolved is not None:
            component_file[name] = resolved
    routes: Dict[str, Path] = {}
    for match in _ROUTE_ROW_RE.finditer(text):
        hash_path, component = match.group(1), match.group(2)
        if component in component_file:
            key = "/" if hash_path in ("", "/") else "/" + hash_path.strip("/")
            routes[key] = component_file[component]
    return routes


def hash_paths_named(text: str) -> set:
    return {(m.group(1) or "/") for m in _HASH_RE.finditer(text)}


def spec_files(app_dir: Path) -> List[Path]:
    tests_dir = app_dir / "tests"
    if not tests_dir.is_dir():
        return []
    return sorted(tests_dir.glob("*.spec.ts"))


def spec_closures(app_dir: Path, routes: Dict[str, Path]) -> Dict[Path, set]:
    all_screens = frozenset(routes.values())
    closures: Dict[Path, set] = {}
    for spec in spec_files(app_dir):
        own = import_closure(spec)
        text = strip_comments(spec.read_text(encoding="utf-8"))
        if "routesFromNav(" in text:
            for screen in all_screens:
                own |= import_closure(screen)
        else:
            for hash_path in hash_paths_named(text):
                screen = routes.get(hash_path)
                if screen is not None:
                    own |= import_closure(screen)
        closures[spec.resolve()] = own
    return closures


def shared_surface(app_dir: Path, routes: Dict[str, Path]) -> set:
    """Files that, touched, mean every spec — see the header above for the derivation."""
    src = app_dir / "src"
    shared: set = set()
    all_screens = frozenset(routes.values())
    app_tsx = src / "App.tsx"
    main_tsx = src / "main.tsx"
    if app_tsx.is_file():
        shared |= import_closure(app_tsx, exclude=all_screens)
    if main_tsx.is_file():
        shared |= import_closure(main_tsx, exclude=frozenset({app_tsx.resolve()}))
    kit_dir = src / "kit"
    if kit_dir.is_dir():
        shared |= {p.resolve() for p in kit_dir.rglob("*") if p.is_file()}
    for name in ("tokens.css", "base.css"):
        candidate = src / name
        if candidate.is_file():
            shared.add(candidate.resolve())
    index_html = app_dir / "index.html"
    if index_html.is_file():
        shared.add(index_html.resolve())
    public_dir = app_dir / "public"
    if public_dir.is_dir():
        shared |= {p.resolve() for p in public_dir.rglob("*") if p.is_file()}
    tests_dir = app_dir / "tests"
    if tests_dir.is_dir():
        for candidate in tests_dir.iterdir():
            if candidate.is_file() and not candidate.name.endswith(".spec.ts"):
                shared.add(candidate.resolve())
    for name in ("playwright.config.ts", "design-check-reporter.ts", "devPort.ts"):
        candidate = app_dir / name
        if candidate.is_file():
            shared.add(candidate.resolve())
    for name in ("package.json", "package-lock.json"):
        candidate = app_dir / name
        if candidate.is_file():
            shared.add(candidate.resolve())
    if app_dir.is_dir():
        shared |= {p.resolve() for p in app_dir.glob("tsconfig*.json")}
    return shared


# `SCOPE` entries outside `app/**` — anything a spec allow-list narrows within `app/**` still
# has to answer to the suite's OTHER dependencies, which `SCOPE` already lists.
_NON_APP_SCOPE = tuple(entry for entry in SCOPE if entry["path"] != "app/**")


def _touches_non_app_scope(changed: Sequence[str]) -> Optional[str]:
    outside = [p for p in changed if not matches("app/**", p)]
    if not outside:
        return None
    verdict = classify_paths(outside, lambda side, path: None, scope=_NON_APP_SCOPE,
                              subject="a shared, non-`app/` dependency", noun="the selection")
    return None if not verdict.run else "a changed path outside app/** is in SCOPE"


class SpecVerdict(NamedTuple):
    specs: List[str]  # relative paths under app/tests/, or [] when `all` is meant
    all_specs: bool
    lines: List[str]


def specs_for_changed_paths(changed: Sequence[str], root: Path = ROOT) -> SpecVerdict:
    app_dir = root / "app"
    lines: List[str] = []

    if os.environ.get("PKMNSCAN_BROWSER_SCOPE") == "off":
        return SpecVerdict([], True, ["PKMNSCAN_BROWSER_SCOPE=off — every spec selected."])

    if not changed:
        return SpecVerdict([], True, [
            "no changed files were found. That is more likely a wrong base than an empty "
            "change, so every spec is selected."])

    whitespace_hit = next((p for p in changed if any(ch.isspace() for ch in p)), None)
    if whitespace_hit is not None:
        return SpecVerdict([], True, [
            f"{whitespace_hit!r} carries whitespace — PW_ARGS is word-split by make, so it "
            "cannot be named to it. Every spec is selected."])

    non_app_reason = _touches_non_app_scope(changed)
    if non_app_reason is not None:
        return SpecVerdict([], True, [non_app_reason + " — every spec is selected."])

    routes = route_map(app_dir)
    closures = spec_closures(app_dir, routes)
    shared = shared_surface(app_dir, routes)

    all_specs = sorted(str(p.relative_to(root)) for p in closures)
    selected: set = set()
    reached_by_none: List[str] = []
    for changed_path in changed:
        if not matches("app/**", changed_path):
            continue  # already covered by _touches_non_app_scope above
        resolved = (root / changed_path).resolve()
        if resolved in shared:
            lines.append(f"  ALL   {changed_path}  (a shared surface)")
            return SpecVerdict([], True, lines + ["a shared surface changed — every spec is "
                                                   "selected."])
        hit_any = False
        for spec, files in closures.items():
            if resolved in files:
                selected.add(str(spec.relative_to(root)))
                hit_any = True
        if hit_any:
            lines.append(f"  some  {changed_path}")
        else:
            reached_by_none.append(changed_path)
            lines.append(f"  ???   {changed_path}  (no spec's derived closure reaches this)")

    if reached_by_none:
        return SpecVerdict([], True, lines + [
            f"{len(reached_by_none)} changed path(s) under app/** reach no spec's derived "
            "closure — the map is a gap, never a license to skip. Every spec is selected."])

    ordered = sorted(selected)
    lines.append(f"{len(ordered)} of {len(all_specs)} specs reached: " +
                 (", ".join(ordered) if ordered else "(none)"))
    return SpecVerdict(ordered, False, lines)


def write_specs_output(verdict: SpecVerdict) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    value = SELECT_ALL if verdict.all_specs else " ".join(verdict.specs)
    partial = "false" if verdict.all_specs else "true"
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(f"specs={value}\n")
        handle.write(f"partial={partial}\n")


def specs_command(base: Optional[str], head: str) -> int:
    if base is None:
        base = "origin/main"
    start = landing_base(base, head)
    if start is None:
        verdict = SpecVerdict([], True, [f"no merge-base between {base} and {head} — every "
                                          "spec is selected."])
    else:
        paths = changed_paths(start, head)
        if paths is None:
            verdict = SpecVerdict([], True, [f"`git diff {start[:12]} {head}` failed — every "
                                              "spec is selected."])
        else:
            verdict = specs_for_changed_paths(paths)
    for line in verdict.lines:
        print(line)
    write_specs_output(verdict)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            if verdict.all_specs:
                handle.write("partial: false (every spec)\n")
            else:
                handle.write(f"partial: {len(verdict.specs)} of "
                             f"{len(spec_files(ROOT / 'app'))} specs\n")
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

    print("\nthe spec allow-list, over the real tree")
    kit_case = specs_for_changed_paths(["app/src/kit/Icon.tsx"])
    ok(kit_case.all_specs, "a shared path under app/src/kit/ selects every spec")

    inv_case = specs_for_changed_paths(["app/src/Inventory.tsx"])
    ok(not inv_case.all_specs, "app/src/Inventory.tsx narrows rather than selecting every spec")
    ok("app/tests/inventory.spec.ts" in inv_case.specs,
       "app/src/Inventory.tsx selects inventory.spec.ts")
    ok(any(s in inv_case.specs for s in
           ("app/tests/cursor.spec.ts", "app/tests/page-edge.spec.ts",
            "app/tests/wide.spec.ts", "app/tests/copy-budget.spec.ts",
            "app/tests/button-stack.spec.ts")),
       "app/src/Inventory.tsx selects the routesFromNav( sweeping specs")
    ok("app/tests/review.spec.ts" not in inv_case.specs,
       "app/src/Inventory.tsx does NOT select review.spec.ts")

    unknown_case = specs_for_changed_paths(["app/src/no-such-file-ever.tsx"])
    ok(unknown_case.all_specs, "an unknown app/ path selects every spec")

    os.environ["PKMNSCAN_BROWSER_SCOPE"] = "off"
    try:
        off_case = specs_for_changed_paths(["app/src/Inventory.tsx"])
    finally:
        del os.environ["PKMNSCAN_BROWSER_SCOPE"]
    ok(off_case.all_specs, "PKMNSCAN_BROWSER_SCOPE=off selects every spec")

    space_case = specs_for_changed_paths(["app/src/Inventory .tsx"])
    ok(space_case.all_specs, "a path with whitespace selects every spec")

    empty_case = specs_for_changed_paths([])
    ok(empty_case.all_specs, "an empty diff selects every spec")

    nonapp_case = specs_for_changed_paths(["Makefile"])
    ok(nonapp_case.all_specs,
       "a non-app/ path already in SCOPE (the Makefile) selects every spec")

    docs_case = specs_for_changed_paths(["docs/DECISIONS.md"])
    ok(not docs_case.all_specs and docs_case.specs == [],
       "a docs-only path outside app/ and outside SCOPE selects no spec")

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
    specs_p = sub.add_parser("specs", help="which spec files a partial run needs")
    specs_p.add_argument("--base", help="a revision; the merge-base against --head is the start")
    specs_p.add_argument("--head", default="HEAD")
    sub.add_parser("selftest", help="prove the matcher and the narrowing")
    args = parser.parse_args(argv)

    if args.command == "list":
        for entry in SCOPE:
            within = f"  (within {entry['within']})" if entry.get("within") else ""
            print(f"{entry['path']}{within}\n    {entry['why']}\n")
        return 0
    if args.command == "history":
        return history(args.count)
    if args.command == "specs":
        return specs_command(args.base, args.head)
    if args.command == "selftest":
        return selftest()

    verdict = classify_event(args.event, args.base, args.head)
    for line in verdict.lines:
        print(line)
    write_output(verdict.run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
