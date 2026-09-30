"""Self-test cases, paths commands rows, part 1. Called by `selftest.self_test`."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import List, Set

from .core import ROOT, Report, markdown_files, read, rel
from .paths_commands import (
    _MAKE_REF_RE,
    _MAKE_RULE_RE,
    check_paths,
    ignored_paths,
    iter_code_lines,
    make_target_refs,
    marked_proposed,
    ts_symbols,
)


def run(ok) -> None:
    print("\npath check fires on a dangling reference")
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "fake.md"
        doc.write_text("see `harness/no_such_file.py` for details\n", encoding="utf-8")
        report = Report()
        check_paths(report, [doc], {})
        findings = report.checks[0].findings
        ok(len(findings) == 1, "one finding for one dangling path", str(findings))

        doc.write_text("see `harness/run.py` for details\n", encoding="utf-8")
        report = Report()
        check_paths(report, [doc], {})
        findings = report.checks[0].findings
        ok(not findings, "no finding for a path that resolves", str(findings))

    print("\nignored_paths answers a candidate git refuses to walk past a symlink")
    with tempfile.TemporaryDirectory() as tmp:
        # A REAL THROWAWAY REPO WITH A REAL SYMLINK, reproducing 2026-09-12's failure
        # exactly rather than mocking subprocess — `git check-ignore` genuinely refuses a
        # pathspec that walks past a symlink, and no fake can stand in for its exit code.
        repo = Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
        # NO TRAILING SLASH, matching this repo's own .gitignore and for the same reason
        # (see its header comment): a directory-only pattern does not match a SYMLINK at
        # that name, which is exactly what a worktree puts there.
        (repo / ".gitignore").write_text("harness/images\n", encoding="utf-8")
        (repo / "harness").mkdir()
        target = Path(tmp) / "elsewhere"
        (target / "images" / "images").mkdir(parents=True)
        (repo / "harness" / "images").symlink_to(target / "images")

        direct_code = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=str(repo),
            input=b"harness/images/images",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        ok(direct_code not in (0, 1), "the fixture reproduces the symlink refusal", str(direct_code))

        found = ignored_paths(["harness/images/images"], root=repo)
        ok(
            "harness/images/images" in found,
            "a path beneath a symlinked, gitignored ancestor is recognised as ignored",
            str(found),
        )

        # AND THE OTHER DIRECTION, so the ancestor walk cannot be mistaken for "anything
        # under a symlink is forgiven" — it must still answer NO when the ancestor itself
        # is real content, not an ignore pattern.
        (repo / "harness" / "images" / ".gitignore").unlink(missing_ok=True)
        (repo / ".gitignore").write_text("", encoding="utf-8")
        found_real = ignored_paths(["harness/images/nope"], root=repo)
        ok(
            "harness/images/nope" not in found_real,
            "a symlinked ancestor that is NOT ignored is not swept in with it",
            str(found_real),
        )

    print("\ncommand references need a fence or backticks")
    prose = "T5 and T6 make it **six**. Em-dashes make it a worse OCR target."
    ok(
        not list(iter_code_lines(prose)),
        "`make it` in prose is not a build target",
        str(list(iter_code_lines(prose))),
    )
    backticked = "Run `make harness` before you tell me something works."
    found = [name for _, line in iter_code_lines(backticked) for name in _MAKE_REF_RE.findall(line)]
    ok(found == ["harness"], "backticked `make harness` is", str(found))
    fenced = "```\nmake harness        # all six verification tests\n```"
    found = [name for _, line in iter_code_lines(fenced) for name in _MAKE_REF_RE.findall(line)]
    ok(found == ["harness"], "fenced make harness is", str(found))

    print("\nmake targets: a code span counts unless `make` follows a verb-lead word (S4, amended after review)")
    owner_quote = 'The owner said `"We just need to make capping only be available"` today.'
    found = [name for _, _, m in make_target_refs(owner_quote) for name in [m.group(1)]]
    ok(
        found == [],
        "an owner quote in backticks that contains `make` mid-sentence, right after `to`, "
        "is never read as a target reference",
        str(found),
    )
    real_ref = "Run `make harness` before you tell me something works."
    found = [name for _, _, m in make_target_refs(real_ref) for name in [m.group(1)]]
    ok(found == ["harness"], "a span that starts with `make ` still names a target", str(found))
    proposed = "`+make opsec-selftest` — a target a proposal would add."
    matches = list(make_target_refs(proposed))
    ok(
        len(matches) == 1 and matches[0][2].group(1) == "opsec-selftest"
        and marked_proposed(matches[0][1], matches[0][2].start()),
        "a `+make` proposed reference is still read, sigil and all",
        str(matches),
    )
    two_spans = "See `docs/GATES.md` beside `make icloud-sweep` for the run."
    found = [name for _, _, m in make_target_refs(two_spans) for name in [m.group(1)]]
    ok(
        found == ["icloud-sweep"],
        "two adjacent spans are judged independently: the path span names no target, and "
        "the make span still does",
        str(found),
    )
    still_fenced = "```\n# a session may make things worse: make harness catches it\n```"
    found = [name for _, _, m in make_target_refs(still_fenced) for name in [m.group(1)]]
    ok(
        found == ["things", "harness"],
        "a fenced line is UNCHANGED by this fix: `make things`, mid-line prose inside the "
        "fence, is still read the old way, same as `make harness` right beside it",
        str(found),
    )

    # RED BEFORE THE FIRST CUT OF S4: these four real shapes went invisible when the row
    # required a span to START WITH `make ` — the review caught them the day this landed.
    # None of them starts with `make `, and none of them is an English sentence naming
    # `make` as its verb, so all four must still resolve.
    bash_span = "Grant `Bash(make harness)` in settings."
    found = [name for _, _, m in make_target_refs(bash_span) for name in [m.group(1)]]
    ok(found == ["harness"], "`Bash(make X)` is a command, not a sentence", str(found))
    time_span = "MEASURED, BEFORE AND AFTER. `time make harness` on this tree: 24.85s."
    found = [name for _, _, m in make_target_refs(time_span) for name in [m.group(1)]]
    ok(found == ["harness"], "`time make X`: a shell verb in front of `make` is still a command", str(found))
    shell_c_span = "its subject was `zsh -c '… make server 2>&1 | tail -20'`, a pipeline"
    found = [name for _, _, m in make_target_refs(shell_c_span) for name in [m.group(1)]]
    ok(found == ["server"], "`make` after a quote and an ellipsis inside a shell -c string is still a command", str(found))
    copy_span = "Then the path `/graveyard`, then `Rebuild it with make demo.`, then `Try again`."
    found = [name for _, _, m in make_target_refs(copy_span) for name in [m.group(1)]]
    ok(found == ["demo"], "quoted on-screen copy naming a real target is still read", str(found))

    def _refs_only(text: str) -> List[str]:
        makefile_targets = set(_MAKE_RULE_RE.findall(read(ROOT / "Makefile")))
        return [m.group(1) for _, _, m in make_target_refs(text) if m.group(1) not in makefile_targets]

    ok(_refs_only(owner_quote) == [], "the owner quote names no missing target")
    ok(
        _refs_only("See `make totally-not-a-real-target` here.")
        == ["totally-not-a-real-target"],
        "a real code span naming a missing target is still caught",
    )
    ok(
        _refs_only("Grant `Bash(make definitely-not-a-real-target)` in settings.")
        == ["definitely-not-a-real-target"],
        "RED: `Bash(make <missing-target>)` is still caught, the exact case the review named",
    )
    ok(
        _refs_only("`time make definitely-not-a-real-target` on this tree.")
        == ["definitely-not-a-real-target"],
        "RED: `time make <missing-target>` is still caught",
    )

    print("\nmake targets: no real reference dropped, over the whole tracked tree (S4 review)")
    old_makefile_targets = set(_MAKE_RULE_RE.findall(read(ROOT / "Makefile")))

    def _old_refs(text: str) -> Set[str]:
        # The behaviour before EITHER cut of S4: any `make <word>` anywhere in a backtick
        # span or a fenced line, with no exclusion at all.
        found: Set[str] = set()
        for _, line in iter_code_lines(text):
            found.update(_MAKE_REF_RE.findall(line))
        return found

    def _new_refs(text: str) -> Set[str]:
        return {m.group(1) for _, _, m in make_target_refs(text)}

    dropped_anywhere = False
    for doc_path in markdown_files():
        doc_text = read(doc_path)
        missing = _old_refs(doc_text) - _new_refs(doc_text)
        # A dropped name is only a real regression if IT NAMES A REAL TARGET — the whole
        # point of S4 is that a name naming NOTHING real (an English sentence's object) is
        # correctly dropped, and the corpus has exactly one of those on purpose (D007).
        real_missing = missing & old_makefile_targets
        if real_missing:
            dropped_anywhere = True
            print(f"    DROPPED in {rel(doc_path)}: {sorted(real_missing)}")
    ok(not dropped_anywhere,
       "no real target reference in the whole tracked tree is read by the old rule and "
       "missed by the new one")

    print("\nmodule.attribute references are resolved, not guessed")
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "fake.md"
        doc.write_text("`pipeline/variant.resolve` is used unchanged.\n", encoding="utf-8")
        report = Report()
        check_paths(report, [doc], {})
        findings = report.checks[0].findings
        ok(not findings, "a real module.function resolves", str(findings))

        doc.write_text("`pipeline/variant.no_such_function` does the work.\n", encoding="utf-8")
        report = Report()
        check_paths(report, [doc], {})
        findings = report.checks[0].findings
        ok(len(findings) == 1, "a function that is not defined is reported", str(findings))

    print("\nmodule.attribute falls through to TypeScript when no .py module exists")
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "fake.md"
        # `app/src/server.ts.describeFailure` — the exact shape the fallback used to get
        # wrong: `.describeFailure` is not in KNOWN_SUFFIXES, so `target.with_suffix(".py")`
        # is tried first (never exists here), and the reader must move on to `.ts` rather
        # than reporting a missing file over a symbol that is real.
        doc.write_text("`app/src/server.ts.describeFailure` formats the toast.\n", encoding="utf-8")
        report = Report()
        check_paths(report, [doc], {})
        ok(not report.checks[0].findings,
           "a real exported TS function resolves through the .ts fallback",
           str(report.checks[0].findings))

        doc.write_text("`app/src/server.ts.noSuchExport` formats the toast.\n", encoding="utf-8")
        report = Report()
        check_paths(report, [doc], {})
        ok(len(report.checks[0].findings) == 1,
           "a TS symbol that is not defined is reported, not silently accepted",
           str(report.checks[0].findings))

    print("\nts_symbols reads top-level exports and refuses what it cannot see")
    with tempfile.TemporaryDirectory() as tmp:
        ts = Path(tmp) / "thing.ts"
        ts.write_text(
            "export function realOne() { return 1; }\n"
            "const notExported = 2;\n"
            "  function indented() { return 3; }\n"  # not column-0: must be invisible
            "export const anotherReal = 4;\n",
            encoding="utf-8",
        )
        names = ts_symbols(ts)
        ok("realOne" in names and "anotherReal" in names,
           "top-level export function and export const are both found", str(names))
        ok("indented" not in names,
           "an indented (non-top-level) function is not claimed", str(names))
        ok("neverDefined" not in names,
           "an absent symbol is refused, not guessed", str(names))
