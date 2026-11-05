"""Self-test cases, status reach rows. Called by `selftest.self_test`."""

from __future__ import annotations

from .core import ROOT, claude_and_rules, exists, read
from .design import COLOR, TYPEFACE, token_value
from .hygiene import _VERDICT_CONFIG, _VERDICT_REPORTER, verdict_disagreements
from .paths_commands import phony_gaps
from .status_reach import model_disagreement


def run(ok) -> None:
    # And the live tree, which is what the row actually asserts on every run.
    ok(
        not verdict_disagreements(
            read(_VERDICT_REPORTER) if exists(_VERDICT_REPORTER) else None,
            read(_VERDICT_CONFIG) if exists(_VERDICT_CONFIG) else None,
            read(ROOT / "Makefile"),
            claude_and_rules(),
        ),
        "this repo's own four files agree",
    )

    # A target absent from .PHONY is a green `make` that ran nothing, and nothing in the
    # prose is wrong when it happens — so no other check in this file can see it.
    print("\nevery make target is declared .PHONY")
    complete = ".PHONY: help harness\n\nhelp:\n\t@echo hi\n\nharness:\n\t@run\n"
    ok(phony_gaps(complete) == (set(), set()), "a complete .PHONY is clean", str(phony_gaps(complete)))
    dropped = ".PHONY: help\n\nhelp:\n\t@echo hi\n\nharness:\n\t@run\n"
    ok(
        phony_gaps(dropped) == ({"harness"}, set()),
        "a target missing from .PHONY is reported",
        str(phony_gaps(dropped)),
    )
    stale = ".PHONY: help harness ghost\n\nhelp:\n\t@echo hi\n\nharness:\n\t@run\n"
    ok(
        phony_gaps(stale) == (set(), {"ghost"}),
        "a .PHONY name with no rule is reported",
        str(phony_gaps(stale)),
    )
    ok(
        phony_gaps(read(ROOT / "Makefile")) == (set(), set()),
        "this repo's own Makefile agrees with its .PHONY",
        str(phony_gaps(read(ROOT / "Makefile"))),
    )

    # The token row's silent failures, in the order they would bite: a normaliser that
    # hides a real difference, a parser that reads a value the browser never sees, and a
    # comparison that runs in one direction only.
    print("\nthe locked palette is compared against the stylesheet, both ways")
    ok(
        token_value(COLOR, "#FFF") == token_value(COLOR, "#ffffff"),
        "case and shorthand are spelling, not disagreement",
        f'{token_value(COLOR, "#FFF")} vs {token_value(COLOR, "#ffffff")}',
    )
    ok(
        token_value(TYPEFACE, "'Cabinet Grotesk', sans-serif") == token_value(TYPEFACE, "Cabinet Grotesk"),
        "the generic fallback in a font stack is not part of the token",
        token_value(TYPEFACE, "'Cabinet Grotesk', sans-serif"),
    )

    print("\nthe paid-read model named in CLAUDE.md is the one the code emits")
    rule = "- **Batch API, not sequential calls.** Model: `m-1`."
    ok(model_disagreement(rule, 'MODEL = "m-1"\n') is None, "equal ids agree")
    ok(model_disagreement(rule, 'MODEL = "m-2"\n') is not None, "a swapped model id is caught")
    ok(
        model_disagreement(claude_and_rules(), read(ROOT / "identify" / "prompt.py")) is None,
        "this repo's CLAUDE.md (and its rule files) and prompt.py agree",
    )
    status_reads_gates_not_map(ok)
    status_sources_see_a_deleted_tracks_file(ok)


def status_reads_gates_not_map(ok) -> None:
    """`make status` takes Shipped and Open from the gates corpus, and asks for no retired map module.

    status.py has no self-test of its own. Its docstring names this row, the status-sources check, as the
    audit that holds its reader contract, so the case lives here. THE FIXTURE HAS NO retired map module.
    It holds scripts/status.py, its gates reader and the decision-context hook that status loads, plus the
    gates corpus with one shipped step and one open step. Each assert below names one cause.
    """
    import shutil
    import subprocess
    import sys

    from .selftest_paths_commands_2 import _run_folder

    print("\nmake status reads Shipped and Open from the gates corpus")
    with _run_folder() as run_dir:
        fx = run_dir / "status"
        (fx / "scripts").mkdir(parents=True)
        for name in ("status.py", "gates_corpus.py", "decision-context.py"):
            shutil.copy(ROOT / "scripts" / name, fx / "scripts" / name)
        gates = fx / "docs" / "gates" / "steps"
        gates.mkdir(parents=True)
        (gates / "step001-alpha.md").write_text(
            "1. ~~Alpha shipped fixture title~~ — done.\n", encoding="utf-8")
        (gates / "step002-beta.md").write_text(
            "2. **Beta open fixture title** — not started.\n", encoding="utf-8")
        (fx / "docs" / "gates" / "ORDER.json").write_text(
            '{"order": ["steps/step001-alpha.md", "steps/step002-beta.md"], "tests": [],'
            ' "steps": {"shipped": ["step001"], "open": ["step002"]}}\n',
            encoding="utf-8",
        )
        done = subprocess.run(
            [sys.executable, str(fx / "scripts" / "status.py")], cwd=fx,
            capture_output=True, text=True, timeout=300,
        )
        out = done.stdout + done.stderr
        ok("MISSING: docs/map.py" not in out,
           "make status does not ask for the retired map module",
           "\n".join(line for line in out.splitlines() if "docs/map.py" in line)[:400])
        ok("Alpha shipped fixture title" in out and "Beta open fixture title" in out,
           "make status prints the shipped and the open step from docs/gates/",
           f"rc {done.returncode}: {out.strip()[-400:]}")


def status_sources_see_a_deleted_tracks_file(ok) -> None:
    """The status-sources row sees a deleted tracks file, with no citation of it left in the fixture.

    Main's map carried TRACKS, and the row caught its deletion because SOURCES declared that map with
    TRACKS among its requires. The tracks file holds that data now, so SOURCES has to declare the file.
    THE FIXTURE holds only scripts/status.py: no tracks file and no citation of one, so no other row can
    see the deletion. The control is another declared source that is absent (the decisions index), which
    the row reports today, so the fixture is read. Each assert names one cause.
    """
    import shutil

    from . import status_reach
    from .core import Report
    from .selftest_paths_commands_2 import _run_folder, _swapped

    print("\nthe status-sources row sees a deleted tracks file")
    with _run_folder() as run_dir:
        fx = run_dir / "status-sources"
        (fx / "scripts").mkdir(parents=True)
        shutil.copy(ROOT / "scripts" / "status.py", fx / "scripts" / "status.py")
        report = Report()
        with _swapped(status_reach, ROOT=fx, STATUS=fx / "scripts" / "status.py"):
            status_reach.check_status_sources(report)
    findings = report.checks[0].findings
    ok(any("docs/decisions/ORDER.json" in f.where for f in findings),
       "control: a declared source that is absent is a finding, so the row reads this fixture",
       "\n".join(f.where for f in findings[:6]))
    ok(any("docs/tracks.json" in f.where for f in findings),
       "deleting the tracks file is a finding of the status-sources row",
       f"{len(findings)} findings, none names the tracks file")
