#!/usr/bin/env python3
"""Docs staleness audit — the mechanical half. See docs/decisions/ D16.

This repo's markdown carries its architecture and its rationale. Nothing verified it until
this script existed, so every path, target, subcommand, test id and decision number in it
was true only for as long as someone remembered.

THE AUDIT NEVER WRITES. It opens, compares, prints, and sets an exit code. The only writes
in this file are inside `--self-test`, into a `tempfile.TemporaryDirectory()` it creates
and destroys; nothing on the audit path can touch a tracked file. Adding a `--fix` flag is
a design change, not a knob — a tool that can edit the docs to make its own check pass is
a tool that converts the project's memory into fiction. Same reason it parses with `ast`
instead of importing: importing a project module runs its top-level code, and "read-only"
should mean read-only.

Two severities, split by how knowable each finding is:

  MECHANICAL (exit 1)  a reference is provably wrong. A path that does not resolve, a
                       `make` target that does not exist, a threshold that disagrees with
                       docs/GATES.md. No judgment involved, so it blocks.
  ADVISORY   (exit 2)  a question. Code changed and the doc that describes it did not.
                       Prints and allows: blocking on a question trains you to reach for
                       `git commit --no-verify`, which also disables the opsec guard.
  USAGE      (exit 64) this script was invoked wrongly. NOT 2, and that is the whole point:
                       argparse exits 2 by default, which is the code the pre-commit hook
                       prints-and-allows on. A caller that grew a stale flag would land in
                       the allow branch and read as the routine coupling question — the
                       gate switching itself off while looking entirely normal. 64 falls
                       through to the hook's "the auditor is broken" branch, which is loud.
                       The `audit invocation` check exists so it does not get that far.

THE ROWS LIVE IN THE `docs_audit` PACKAGE BESIDE THIS FILE, one module per group, and
`docs_audit/rows.py` names each row with its tier. This file keeps the command line:
`build_parser` and `main`. It also carries every name the package defines, so a caller that
loads it by path still finds them; it moves the tree with `set_root`, never by assigning
`ROOT` here. See D16.

Stdlib only, so the git hook can call `python3` directly and never depends on `make venv`
having been run.

    scripts/docs-audit.py              audit the whole tree
    scripts/docs-audit.py --staged     audit the staged set (what the pre-commit hook runs)
    scripts/docs-audit.py --self-test  prove the extractors work before trusting a report

Escape hatch: BANCHI_DOCS=off, honored by the hook. Deliberate, visible in your shell, and unlike editing this file it
does not change what the check means.

One more environment variable, and it is the opposite of an escape hatch:

    BANCHI_EXPORTS   colon-separated paths to extra TCGplayer Filtered CSV exports,
                       absolute or repo-relative. The game-registry rows read the committed
                       fixtures always; this adds files the repo cannot carry — a
                       full-catalog export, a Riftbound one — so their coverage questions
                       get asked. IT WIDENS THE ADVISORY ROW AND NOTHING ELSE. A path that
                       does not resolve is skipped in silence, and nothing read through it
                       can fail a commit: a gate that a file on one person's disk can break
                       is a gate that gets switched off, and a gate that *needs* such a file
                       has already switched itself off for everybody else.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

# THE AUDIT NEVER WRITES, and an imported package would leave bytecode beside its modules on every
# run; the single file this replaced was never cached. So nothing is.
sys.dont_write_bytecode = True

_SCRIPTS = str(Path(__file__).resolve().parent)
sys.path.insert(0, _SCRIPTS)
try:
    import docs_audit
    from docs_audit.core import EXIT_USAGE
    from docs_audit.rows import audit
    from docs_audit.selftest import self_test
finally:
    sys.path.remove(_SCRIPTS)

# The rows that check this command line ask for its parser here, so the parser stays in this file.
docs_audit.core.entry_parser_hook = lambda: build_parser()

# EVERY NAME THE ONE-FILE SCRIPT HAD IS STILL ON THIS MODULE. Callers load this file by path and
# read its functions (`markdown_files`, `cited_decisions`, `Report`, ...), so the package is
# copied onto it. A copy is a snapshot: `ROOT` is moved with `set_root`, never by assigning here.
for _module in docs_audit.MODULES:
    globals().update({name: value for name, value in vars(_module).items() if not name.startswith("__")})


class _Parser(argparse.ArgumentParser):
    """Usage errors exit EXIT_USAGE, never argparse's default 2.

    2 is this script's advisory code and the pre-commit hook prints-and-allows on it, so
    argparse's default would let a stale flag in a caller disable the commit gate while
    printing something that reads like the routine coupling question.
    """

    def error(self, message: str):  # pragma: no cover - argparse contract
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        sys.exit(EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="docs-audit",
        description="Audit the markdown for stale references. Never writes.",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="audit the staged set and run the coupling question (what the hook runs)",
    )
    parser.add_argument(
        "--all", action="store_true", help="audit every markdown file (the default)"
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Tier 1 rows only (L12, test-audit plan): what the pre-commit hook passes. "
             "Tier 2 and 3 rows are skipped entirely, never computed. Omit for CI's full run.",
    )
    parser.add_argument("--self-test", action="store_true", help="verify the extractors and exit")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print one JSON object — rows plus the exit code — instead of the human render",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.self_test:
        return self_test()

    report = audit(staged_only=args.staged, commit_only=args.commit)
    mechanical, advisory = report.counts()
    code = 1 if mechanical else 2 if advisory else 0
    print(report.as_json(code) if args.json else report.render())
    return code


if __name__ == "__main__":
    sys.exit(main())
