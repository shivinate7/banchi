"""Self-test cases, code invariants rows, part 3. Called by `selftest.self_test`."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

from .code_invariants import (
    CODE_AGREEMENT_ARM_COUNT,
    check_column_counts,
    check_dist_path_agreement,
    check_import_filename_agreement,
    check_threshold_agreement,
)
from .core import Finding, PACKAGE_DIR, ROOT, Report, markdown_files, module_globals
from .paths_commands import _commands_named, _commands_roster_findings, check_commands_roster
from .registry_scopes import CHECKS_REGISTRY, check_commit_path


def run(ok) -> None:
    # ------------------------------------------------------------------- markdown_files
    print("\nmarkdown_files: the tracked tree only, so a scratch file fails no row")
    # Patched through `module_globals()`, never a `global` statement: this function may read
    # both names earlier, and a `global` after a use is a syntax error.
    here = module_globals()
    saved_walk, saved_nul = here["_walk"], here["_nul_list"]
    try:
        here["_walk"] = lambda root, suffixes: [ROOT / "docs" / "kept.md", ROOT / "scratch.md"]
        here["_nul_list"] = lambda *args: {"docs/kept.md", "README.md"}
        ok(markdown_files() == [ROOT / "docs" / "kept.md"],
           "RED before the fix: an untracked scratch .md in the worktree is not read",
           f"{markdown_files()}")
        here["_nul_list"] = lambda *args: set()
        ok(markdown_files() == [ROOT / "docs" / "kept.md", ROOT / "scratch.md"],
           "with no git answer it falls back to the walk and reads every file it finds")
    finally:
        here["_walk"], here["_nul_list"] = saved_walk, saved_nul

    # ------------------------------------------------------- code-side agreements
    #
    # Seven arms, each patching its row's own path constant (or, for the table-driven row,
    # one group's site tuple) to a throwaway fixture — the same save/patch/restore-in-
    # `finally` shape used above for `MAP` — and calling the ROW ITSELF, never the bare
    # comparison logic, on `unscoped walk`'s own argument: a fixture-only test proves the
    # matcher works and nothing about whether the row still calls it. `code_agreement_arms`
    # counts how many actually ran, and the last line of this section asserts it against
    # `CODE_AGREEMENT_ARM_COUNT` — raising the constant with no matching arm added, or
    # deleting an arm without lowering it, both fail `--self-test`.
    print("\ncode-side agreements: seven arms across five rows, each proven red on its own fixture")
    code_agreement_arms = 0

    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "tcg_import.py"
        fixture.write_text(
            "from typing import Sequence, Tuple\n\n"
            "# The eleven fields `PricingStagedPrice` reads, mapped from the export's own "
            "column names.\n"
            "COLUMNS: Sequence[Tuple[str, str]] = (\n"
            '    ("A", "a"),\n    ("B", "b"),\n    ("C", "c"),\n'
            ")\n",
            encoding="utf-8",
        )
        _saved = module_globals()["_TCG_IMPORT_PATH"]
        try:
            module_globals()["_TCG_IMPORT_PATH"] = fixture
            report = Report()
            check_column_counts(report)
        finally:
            module_globals()["_TCG_IMPORT_PATH"] = _saved
        by_label = {row.check: row.findings for row in report.checks}
        ok(
            any("eleven" in f.message and "3 pairs" in f.message for f in by_label["column counts"]),
            "column counts: a comment saying `eleven` against a 3-pair tuple fails the row "
            "(the merged `column count` sub-check), naming both",
            str(by_label["column counts"]),
        )
        code_agreement_arms += 1

    with tempfile.TemporaryDirectory() as tmp:
        tsx_fixture = Path(tmp) / "ReviewQueue.tsx"
        tsx_fixture.write_text(
            "/* D9's threshold — `pipeline/pricing.py:THRESHOLD`. */\nconst THRESHOLD = 0.9\n",
            encoding="utf-8",
        )
        py_fixture = Path(tmp) / "pricing.py"
        py_fixture.write_text('THRESHOLD = Decimal("0.40")\n', encoding="utf-8")
        _saved_tsx = module_globals()["_REVIEWQUEUE_PATH"]
        _saved_py = module_globals()["_PRICING_PATH"]
        try:
            module_globals()["_REVIEWQUEUE_PATH"] = tsx_fixture
            module_globals()["_PRICING_PATH"] = py_fixture
            report = Report()
            check_threshold_agreement(report)
        finally:
            module_globals()["_REVIEWQUEUE_PATH"] = _saved_tsx
            module_globals()["_PRICING_PATH"] = _saved_py
        by_label = {row.check: row.findings for row in report.checks}
        ok(
            any("0.9" in f.message and "0.40" in f.message for f in by_label["threshold agreement"]),
            "threshold agreement: a JSX copy that disagrees with pipeline/pricing.py fails "
            "the row, naming both values",
            str(by_label["threshold agreement"]),
        )
        code_agreement_arms += 1

    with tempfile.TemporaryDirectory() as tmp:
        serve_fixture = Path(tmp) / "serve.py"
        serve_fixture.write_text('DIST = "app/build"\n', encoding="utf-8")
        capture_fixture = Path(tmp) / "capture_server.py"
        capture_fixture.write_text(
            'APP_DIST = Path(__file__).resolve().parent.parent / "app" / "dist"\n',
            encoding="utf-8",
        )
        vite_fixture = Path(tmp) / "vite.config.ts"
        vite_fixture.write_text("export default defineConfig({ base: '/' })\n", encoding="utf-8")
        _saved_serve = module_globals()["_SERVE_PATH"]
        _saved_capture = module_globals()["_CAPTURE_SERVER_PATH"]
        _saved_vite = module_globals()["_VITE_CONFIG_PATH"]
        try:
            module_globals()["_SERVE_PATH"] = serve_fixture
            module_globals()["_CAPTURE_SERVER_PATH"] = capture_fixture
            module_globals()["_VITE_CONFIG_PATH"] = vite_fixture
            report = Report()
            check_dist_path_agreement(report)
        finally:
            module_globals()["_SERVE_PATH"] = _saved_serve
            module_globals()["_CAPTURE_SERVER_PATH"] = _saved_capture
            module_globals()["_VITE_CONFIG_PATH"] = _saved_vite
        by_label = {row.check: row.findings for row in report.checks}
        ok(
            any("app/build" in f.message for f in by_label["dist path agreement"]),
            "dist path agreement: scripts/serve.py:DIST disagreeing with `app/dist` fails "
            "the row",
            str(by_label["dist path agreement"]),
        )
        code_agreement_arms += 1

        # A second sub-case on the same arm: an `outDir` appearing in vite.config.ts is
        # itself a finding, with both Python sides otherwise agreeing.
        serve_fixture.write_text('DIST = "app/dist"\n', encoding="utf-8")
        vite_fixture.write_text(
            "export default defineConfig({ build: { outDir: 'build' } })\n", encoding="utf-8"
        )
        try:
            module_globals()["_SERVE_PATH"] = serve_fixture
            module_globals()["_CAPTURE_SERVER_PATH"] = capture_fixture
            module_globals()["_VITE_CONFIG_PATH"] = vite_fixture
            report = Report()
            check_dist_path_agreement(report)
        finally:
            module_globals()["_SERVE_PATH"] = _saved_serve
            module_globals()["_CAPTURE_SERVER_PATH"] = _saved_capture
            module_globals()["_VITE_CONFIG_PATH"] = _saved_vite
        by_label = {row.check: row.findings for row in report.checks}
        ok(
            any("outDir" in f.message for f in by_label["dist path agreement"]),
            "dist path agreement: an `outDir` key in vite.config.ts fails the row even when "
            "both Python sides agree",
            str(by_label["dist path agreement"]),
        )

    with tempfile.TemporaryDirectory() as tmp:
        shipping_fixture = Path(tmp) / "shipping_routes.py"
        shipping_fixture.write_text('IMPORT_FILENAME = "pirateship-import.csv"\n', encoding="utf-8")
        capture_fixture = Path(tmp) / "capture_server.py"
        capture_fixture.write_text(
            "return self._send(HTTPStatus.OK, blob, kind, "
            '((\"Content-Disposition\", \'attachment; filename="import.csv"\'),))\n',
            encoding="utf-8",
        )
        _saved_shipping = module_globals()["_SHIPPING_ROUTES_PATH"]
        _saved_capture = module_globals()["_CAPTURE_SERVER_PATH"]
        try:
            module_globals()["_SHIPPING_ROUTES_PATH"] = shipping_fixture
            module_globals()["_CAPTURE_SERVER_PATH"] = capture_fixture
            report = Report()
            check_import_filename_agreement(report)
        finally:
            module_globals()["_SHIPPING_ROUTES_PATH"] = _saved_shipping
            module_globals()["_CAPTURE_SERVER_PATH"] = _saved_capture
        by_label = {row.check: row.findings for row in report.checks}
        ok(
            any("import.csv" in f.message and "pirateship-import.csv" in f.message
                for f in by_label["import filename agreement"]),
            "import filename agreement: a Content-Disposition header naming a different "
            "file than IMPORT_FILENAME fails the row, naming both",
            str(by_label["import filename agreement"]),
        )
        code_agreement_arms += 1

    ok(
        code_agreement_arms == CODE_AGREEMENT_ARM_COUNT,
        "every code-side agreement row got its own mutation arm",
        f"ran {code_agreement_arms}, pinned {CODE_AGREEMENT_ARM_COUNT}",
    )

    # And end to end, unpatched: the real tree agrees with itself on a clean checkout.
    report = Report()
    check_column_counts(report)
    check_threshold_agreement(report)
    check_dist_path_agreement(report)
    check_import_filename_agreement(report)
    by_label = {row.check: row.findings for row in report.checks}
    for label in ("column counts", "threshold agreement", "dist path agreement", "import filename agreement"):
        ok(not by_label[label], f"the real tree has zero findings on `{label}`", str(by_label[label]))

    print("\ncommands roster: three ways to be documented, and the allow-list only shrinks")
    _targets = {"up", "down", "reap", "venv"}
    _msgs = lambda findings: [f.message for f in findings]  # noqa: E731 - short-lived local
    ok(_commands_roster_findings(_targets, {"up", "down"}, {"reap"}, {"venv": "why"}) == [],
       "a bullet, a `make check` member and an allow-list entry all count as documented")
    _missing = _commands_roster_findings(_targets, {"up"}, set(), {})
    ok(any("down" in m and "reap" in m for m in _msgs(_missing)) is False
       and len(_missing) == 3,
       "a target reaching none of the three ways is refused, one finding per target",
       str(_missing))
    _stale = _commands_roster_findings(_targets, {"up", "down", "reap", "venv"}, set(),
                                        {"up": "used to be internal"})
    ok(any("Stale" in m for m in _msgs(_stale)),
       "an allow-list entry for a target CLAUDE.md now bullets is stale",
       str(_msgs(_stale)))
    _ghost = _commands_roster_findings(_targets, {"up", "down", "reap", "venv"}, set(),
                                        {"no-such-target": "why"})
    ok(any("not a real Makefile target" in m for m in _msgs(_ghost)),
       "an allow-list entry naming a target that does not exist is refused",
       str(_msgs(_ghost)))
    ok(_commands_named("## Commands\n\n```\nmake up   # one line\nmake down # another\n```\n")
       == {"up", "down"},
       "the Commands block's bullet names are read out of its fenced list")

    print("\ncommands roster: end to end, unpatched: the real tree agrees with itself")
    report = Report()
    check_commands_roster(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(not by_label["commands roster"], "the real tree has zero findings on `commands roster`",
       str(by_label["commands roster"]))

    print("\ncommit path: the AST reads the code, MUTATION-TESTED against the real files, "
          "via .bak copies")
    # This is `commit path` going red on the exact defect it exists to guard: `writes` was
    # a sentence nobody checked against the source. Two real, on-commit-path files are
    # mutated in turn — `scripts/sigil-check.py` (to make code write) and `scripts/checks.py`
    # (to make the field lie the other way) — never `git checkout <path>` to undo either,
    # a `.bak` copy is the restore, same discipline as `derived numbers` above.
    sigil_path = ROOT / "scripts" / "sigil-check.py"
    sigil_original = sigil_path.read_text(encoding="utf-8")
    sigil_bak = sigil_path.with_suffix(".py.bak")

    def _run_commit_path() -> List[Finding]:
        fresh = Report()
        check_commit_path(fresh)
        by = {row.check: row.findings for row in fresh.checks}
        return by.get("commit path", [])

    # Arm 1: the founding defect. Code writes; `writes` in checks.py stays "". Two separate
    # mutants, so this is a real kill count and not one lucky match.
    arm1_kills = 0
    arm1_mutants = [
        ('def scan() -> List[Finding]:\n',
         'def scan() -> List[Finding]:\n'
         '    Path("/tmp/sigil-check-selftest-mutant").write_text("mutated")\n'),
        ('def files() -> Iterable[Path]:\n',
         'def files() -> Iterable[Path]:\n'
         '    import shutil as _sh; _sh.copy(__file__, __file__ + ".selftest-mutant")\n'),
    ]
    for old, new in arm1_mutants:
        assert old in sigil_original, "sigil-check.py no longer has the shape this arm mutates"
        mutated = sigil_original.replace(old, new, 1)
        ok(mutated != sigil_original,
           "arm 1 mutation actually changed scripts/sigil-check.py")
        sigil_bak.write_text(sigil_original, encoding="utf-8")
        try:
            sigil_path.write_text(mutated, encoding="utf-8")
            findings = _run_commit_path()
        finally:
            sigil_path.write_text(sigil_original, encoding="utf-8")
            sigil_bak.unlink()
        hit = [f for f in findings
               if f.where.endswith("sigil-check") and "SAYS NOTHING" in f.message]
        if hit:
            arm1_kills += 1
        ok(bool(hit), "a commit-path check whose source now writes, with `writes` still "
           "empty, goes red", str(findings))
    ok(arm1_kills == len(arm1_mutants),
       "arm 1: every write-shaped mutant was killed",
       f"killed {arm1_kills} of {len(arm1_mutants)}")

    # Restored, the real sigil-check.py is clean again on this arm.
    ok(not [f for f in _run_commit_path() if f.where.endswith("sigil-check")],
       "restored from the .bak copy, scripts/sigil-check.py passes `commit path` clean again",
       str(_run_commit_path()))

    # Arm 2: the other direction. `writes` claims something; the real source makes no write
    # this reader can see. `t3_join_coverage`'s own docstring is the argument for checking
    # both ways: "a one-directional check passes on that bug."
    checks_path = CHECKS_REGISTRY
    checks_original = checks_path.read_text(encoding="utf-8")
    checks_bak = checks_path.with_suffix(".py.bak")
    old_field = (
        '        "target": "sigil-check",\n'
        '        "runs": "python3 scripts/sigil-check.py --self-test && python3 '
        'scripts/sigil-check.py",\n'
    )
    assert old_field in checks_original, "sigil-check's entry moved; update this arm's anchor"
    # Flip its OWN `writes: ""` (searched from this anchor forward) to a false claim,
    # leaving every other entry's field untouched.
    anchor = checks_original.index(old_field)
    field_at = checks_original.index('"writes": ""', anchor)
    mutated_checks = (
        checks_original[:field_at]
        + '"writes": "a fixture, invented for this self-test only."'
        + checks_original[field_at + len('"writes": ""'):]
    )
    ok(mutated_checks != checks_original,
       "arm 2 mutation actually changed scripts/checks.py")
    checks_bak.write_text(checks_original, encoding="utf-8")
    try:
        checks_path.write_text(mutated_checks, encoding="utf-8")
        findings = _run_commit_path()
    finally:
        checks_path.write_text(checks_original, encoding="utf-8")
        checks_bak.unlink()
    hit2 = [f for f in findings
            if f.where.endswith("sigil-check") and "reads no write" in f.message]
    ok(bool(hit2),
       "a commit-path check declaring `writes` the AST cannot find on the real source "
       "goes red",
       str(findings))
    ok(not [f for f in _run_commit_path() if f.where.endswith("sigil-check")],
       "restored from the .bak copy, scripts/checks.py passes `commit path` clean again",
       str(_run_commit_path()))

    # Arm 3: scope. The same write-shaped mutant, planted in an OFF-commit-path script,
    # is not this row's business — `claim_stale`'s entry carries `commit_path: False` and a
    # `why_off_commit_path`, and this row must not start grading its writes.
    claim_ids_path = ROOT / "scripts" / "claim-ids.py"
    if claim_ids_path.exists():
        claim_original = claim_ids_path.read_text(encoding="utf-8")
        claim_bak = claim_ids_path.with_suffix(".py.bak")
        needle = "def main("
        idx = claim_original.find(needle)
        ok(idx != -1, "scripts/claim-ids.py has a main() this arm can mutate near")
        if idx != -1:
            insertion_point = claim_original.index("\n", idx) + 1
            mutated_claim = (
                claim_original[:insertion_point]
                + '    Path("/tmp/claim-ids-selftest-mutant").write_text("mutated")\n'
                + claim_original[insertion_point:]
            )
            ok(mutated_claim != claim_original,
               "arm 3 mutation actually changed scripts/claim-ids.py")
            claim_bak.write_text(claim_original, encoding="utf-8")
            try:
                claim_ids_path.write_text(mutated_claim, encoding="utf-8")
                findings = _run_commit_path()
            finally:
                claim_ids_path.write_text(claim_original, encoding="utf-8")
                claim_bak.unlink()
            ok(not [f for f in findings if "claim-stale" in f.where],
               "an off-commit-path check writing is not this row's business — no finding "
               "names it",
               str(findings))

    # Arm 4: the package. `docs-audit.py` is a thin entry point and every row lives in the
    # package beside it, so a write planted in a package function the audit reaches must be
    # found through the entry, or the entry reads as a program of three functions that write
    # nothing. `read` is on every row's path.
    core_path = PACKAGE_DIR / "core.py"
    core_original = core_path.read_text(encoding="utf-8")
    core_bak = core_path.with_suffix(".py.bak")
    core_anchor = "def read(path: Path) -> str:\n"
    ok(core_anchor in core_original, "core.py still has the `read` this arm mutates")
    core_mutated = core_original.replace(
        core_anchor, core_anchor + '    Path("/tmp/docs-audit-selftest-mutant").write_text("mutated")\n', 1)
    core_bak.write_text(core_original, encoding="utf-8")
    try:
        core_path.write_text(core_mutated, encoding="utf-8")
        findings = _run_commit_path()
    finally:
        core_path.write_text(core_original, encoding="utf-8")
        core_bak.unlink()
    ok(any(f.where.endswith("docs-audit") and "SAYS NOTHING" in f.message for f in findings),
       "arm 4: a write planted in a package module the audit reaches goes red on `commit path`",
       str(findings))
    ok(not _run_commit_path(),
       "restored from the .bak copy, the package passes `commit path` clean again",
       str(_run_commit_path()))

    # Arm 5: the honest pair, unmutated. `docs-audit` and `sigil-check` are the only two
    # entries `commit_path: True` names today, and neither should ever produce a finding
    # on a clean tree.
    clean_findings = _run_commit_path()
    ok(clean_findings == [],
       "the real tree's two commit-path checks (docs-audit, sigil-check) pass `commit "
       "path` with zero findings",
       str(clean_findings))
