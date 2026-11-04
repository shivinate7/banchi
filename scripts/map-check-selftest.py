#!/usr/bin/env python3
"""`scripts/map-check.py`'s fail-closed arms, proved against stub skills built here (`make map-check-selftest`).

Protects: the map check never passes without checking. No plain-english-map skill found exits
non-zero. A named CLAUDE_SETTINGS_DIR that holds no skill fails and never falls through to another
copy, and neither does a named dir with a skill folder but no map-check.mjs. node missing exits
non-zero. The skill's own exit code is map-check.py's exit code.
Governs: D18

NO NETWORK, NO REAL SKILL. Each skill is a stub `map-check.mjs` that prints a marker and exits
with `STUB_EXIT`. Every fixture is a folder under this run's run folder (harness/tests/home.py's
`run_folder`, test-temp-standard), removed on exit.

THE MUTANTS. Each is map-check.py with one exact text replaced, built in the run folder. The
default run requires every mutant to turn at least one check red. `--mutant NAME` runs the same
checks on that one mutant and exits 1 when any check goes red, so a red run can be re-run:

    python3 scripts/map-check-selftest.py --mutant no-skill-exit-zero

The subprocess cases run map-check.py with HOME, CLAUDE_SETTINGS_DIR and PATH set per case, so
`main()` reads the same environment a real run reads. The in-process cases call `find_skill`
with an explicit env and home.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REAL = ROOT / "scripts" / "map-check.py"
sys.path.insert(0, str(ROOT))

from harness.tests.home import run_folder  # noqa: E402

SKILL_REL = Path("skills") / "plain-english-map"
MARK = "STUB-RAN"
STUB = "console.log('STUB-RAN');\nprocess.exit(Number(process.env.STUB_EXIT || 0));\n"

MUTANTS = {
    "no-skill-exit-zero": (
        '        return 1\n    if "--where" in argv:',
        '        return 0\n    if "--where" in argv:',
    ),
    "named-falls-through": (
        "        return [Path(named)]",
        "        pass",
    ),
    "node-missing-exit-zero": (
        "        return 1\n    return subprocess.run",
        "        return 0\n    return subprocess.run",
    ),
    "check-exit-swallowed": (
        '    return subprocess.run([node, str(skill / "scripts" / "map-check.mjs")], cwd=ROOT).returncode',
        '    subprocess.run([node, str(skill / "scripts" / "map-check.mjs")], cwd=ROOT)\n    return 0',
    ),
}


class Tally:
    """One line per check. A red check's label is its one cause; `red` lists them for the count."""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self.red: list[str] = []

    def check(self, cond: bool, label: str, detail: str = "") -> None:
        if not cond:
            self.red.append(label)
        if not self.quiet:
            tag = "ok    " if cond else "FAIL  "
            tail = f"  ({detail})" if detail else ""
            print(f"  {tag} {label}{tail}")


def make_mutant(name: str, under: Path):
    """map-check.py with the one exact text of MUTANTS[name] replaced. None when that text is not there once."""
    old, new = MUTANTS[name]
    text = REAL.read_text(encoding="utf-8")
    if text.count(old) != 1:
        return None
    script = under / name / "scripts" / "map-check.py"
    script.parent.mkdir(parents=True)
    script.write_text(text.replace(old, new, 1), encoding="utf-8")
    return script


def load(script: Path):
    spec = importlib.util.spec_from_file_location("map_check_under_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def has_skill(checkout: Path) -> bool:
    return (checkout / SKILL_REL / "scripts" / "map-check.mjs").is_file()


def make_skill(checkout: Path, mjs: bool = True) -> None:
    scripts = checkout / SKILL_REL / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    if mjs:
        (scripts / "map-check.mjs").write_text(STUB, encoding="utf-8")


def fresh(work: Path, name: str) -> Path:
    folder = work / name
    (folder / "home").mkdir(parents=True, exist_ok=True)
    return folder


def run_main(script: Path, home: Path, named=None, path=None, stub_exit=None):
    env = dict(os.environ)
    for key in ("CLAUDE_SETTINGS_DIR", "STUB_EXIT"):
        env.pop(key, None)
    env["HOME"] = str(home)
    if named is not None:
        env["CLAUDE_SETTINGS_DIR"] = str(named)
    if path is not None:
        env["PATH"] = path
    if stub_exit is not None:
        env["STUB_EXIT"] = str(stub_exit)
    done = subprocess.run(
        [sys.executable, str(script)], env=env, capture_output=True, text=True, timeout=120
    )
    return done.returncode, done.stdout, done.stderr


def find_checks(module, work: Path, t: Tally) -> None:
    """`find_skill` and `candidate_roots`, called with an explicit env and home."""
    folder = fresh(work, "find-home-only")
    home = folder / "home"
    make_skill(home / "claude-settings")
    t.check(has_skill(home / "claude-settings"), "fixture: the home claude-settings holds the skill")
    got = module.find_skill(env={}, home=home)
    t.check(got == home / "claude-settings" / SKILL_REL,
            "find_skill returns the home claude-settings skill when no dir is named", f"got {got}")

    folder = fresh(work, "find-named-empty")
    home = folder / "home"
    make_skill(home / "claude-settings")
    named = folder / "named"
    named.mkdir()
    t.check(has_skill(home / "claude-settings"),
            "fixture: the home copy holds the skill, so a fall-through would find it")
    t.check(not has_skill(named), "fixture: the named dir holds no skill")
    got = module.find_skill(env={"CLAUDE_SETTINGS_DIR": str(named)}, home=home)
    t.check(got is None, "a named CLAUDE_SETTINGS_DIR with no skill returns None, never the home copy",
            f"got {got}")

    folder = fresh(work, "find-named-partial")
    home = folder / "home"
    make_skill(home / "claude-settings")
    named = folder / "named"
    make_skill(named, mjs=False)
    t.check((named / SKILL_REL).is_dir() and not has_skill(named),
            "fixture: the named dir has a skill folder and no map-check.mjs")
    got = module.find_skill(env={"CLAUDE_SETTINGS_DIR": str(named)}, home=home)
    t.check(got is None, "a named dir with a partial skill returns None, never the home copy",
            f"got {got}")

    folder = fresh(work, "find-named-holds-skill")
    home = folder / "home"
    make_skill(home / "claude-settings")
    named = folder / "named"
    make_skill(named)
    got = module.find_skill(env={"CLAUDE_SETTINGS_DIR": str(named)}, home=home)
    t.check(got == named / SKILL_REL, "a named dir that holds the skill is the one returned",
            f"got {got}")

    folder = fresh(work, "find-none")
    home = folder / "home"
    t.check(not (home / "claude-settings").exists(), "fixture: the home has no claude-settings")
    got = module.find_skill(env={}, home=home)
    t.check(got is None, "no skill anywhere: find_skill returns None", f"got {got}")


def main_checks(script: Path, work: Path, t: Tally) -> None:
    """map-check.py run as a process, so `main()` reads the environment a real run reads."""
    folder = fresh(work, "main-home-only")
    home = folder / "home"
    make_skill(home / "claude-settings")
    rc, out, err = run_main(script, home)
    t.check(rc == 0 and MARK in out, "control: the home skill with no named dir runs and passes",
            f"rc {rc}, stderr {err.strip()[:160]}")

    folder = fresh(work, "main-none")
    rc, out, err = run_main(script, folder / "home")
    t.check(rc != 0, "no skill found: map-check.py exits non-zero", f"rc {rc}")
    t.check("NOT checked" in err, "no skill found: the message says the map was NOT checked",
            err.strip()[:160])

    folder = fresh(work, "main-named-empty")
    home = folder / "home"
    make_skill(home / "claude-settings")
    named = folder / "named"
    named.mkdir()
    t.check(has_skill(home / "claude-settings"),
            "fixture: the home copy holds the skill, so a fall-through would run it")
    rc, out, err = run_main(script, home, named=named)
    t.check(rc != 0, "a named CLAUDE_SETTINGS_DIR with no skill exits non-zero", f"rc {rc}")
    t.check(MARK not in out, "a named CLAUDE_SETTINGS_DIR with no skill never runs the home copy",
            out.strip()[:160])

    folder = fresh(work, "main-named-partial")
    home = folder / "home"
    make_skill(home / "claude-settings")
    named = folder / "named"
    make_skill(named, mjs=False)
    t.check((named / SKILL_REL).is_dir() and not has_skill(named),
            "fixture: the named dir has a skill folder and no map-check.mjs")
    rc, out, err = run_main(script, home, named=named)
    t.check(rc != 0, "a named dir with a partial skill exits non-zero", f"rc {rc}")
    t.check(MARK not in out, "a named dir with a partial skill never runs the home copy",
            out.strip()[:160])

    folder = fresh(work, "main-named-skill")
    home = folder / "home"
    named = folder / "named"
    make_skill(named)
    no_bin = folder / "no-bin"
    no_bin.mkdir()
    t.check(has_skill(named), "fixture: the named dir holds the skill, so node is the arm under test")
    rc, out, err = run_main(script, home, named=named, path=str(no_bin))
    t.check(rc != 0, "node missing: map-check.py exits non-zero", f"rc {rc}")
    t.check("node is not on PATH" in err, "node missing: the message names node", err.strip()[:160])
    t.check(MARK not in out, "node missing: the skill never runs", out.strip()[:160])

    rc, out, err = run_main(script, home, named=named, stub_exit=3)
    t.check(rc == 3, "the skill's own exit code is map-check.py's exit code", f"rc {rc}")

    rc, out, err = run_main(script, home, named=named)
    t.check(rc == 0 and MARK in out, "control: a named skill with node on PATH runs and passes",
            f"rc {rc}, stderr {err.strip()[:160]}")


def run_checks(script: Path, work: Path, t: Tally) -> None:
    find_checks(load(script), work, t)
    main_checks(script, work, t)


def sweep_check(work: Path, t: Tally) -> None:
    """run_folder's sweep: an old sibling goes, a new one stays, and its own folder goes on exit."""
    root = work / "sweep-root"
    root.mkdir(parents=True)
    old = root / f"1-{uuid.uuid4()}"
    old.mkdir()
    os.utime(old, (0, 0))
    new = root / f"2-{uuid.uuid4()}"
    new.mkdir()
    with run_folder(root=root) as own:
        t.check(not old.exists(), "run_folder removes a sibling run folder over a day old")
        t.check(new.exists(), "run_folder keeps a sibling run folder under a day old")
        t.check(own.is_dir(), "run_folder makes its own run folder")
    t.check(not own.exists(), "run_folder removes its own run folder on exit")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="map-check.py's fail-closed arms, over stub skills.")
    ap.add_argument("--mutant", choices=sorted(MUTANTS),
                    help="run the checks on this one mutant; exit 1 when any check goes red")
    args = ap.parse_args(argv)
    with run_folder() as run:
        if args.mutant:
            t = Tally(quiet=True)
            script = make_mutant(args.mutant, run / "mutants")
            if script is None:
                t.check(False, f"mutant {args.mutant}: its one site is in map-check.py exactly once")
            else:
                run_checks(script, run / "cases", t)
            for cause in t.red:
                print(f"FAIL  {cause}")
            print(f"{args.mutant}: {len(t.red)} failed")
            return 1 if t.red else 0

        t = Tally()
        print("map-check.py as it is:")
        run_checks(REAL, run / "real", t)
        print("run_folder sweep:")
        sweep_check(run / "sweep", t)
        print("mutants, each must turn a check red:")
        for name in MUTANTS:
            script = make_mutant(name, run / "mutants")
            t.check(script is not None, f"mutant {name}: its one site is in map-check.py exactly once")
            if script is None:
                continue
            caught = Tally(quiet=True)
            run_checks(script, run / "cases" / name, caught)
            t.check(bool(caught.red), f"mutant {name} is caught by at least one check",
                    f"{len(caught.red)} checks red")
    return 1 if t.red else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
