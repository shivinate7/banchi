#!/usr/bin/env python3
"""`make explain` — what `make check` runs, and what each row of it is worth.

THE COMPOSITION OF `make check` WAS ARGUED AT LENGTH AND PUBLISHED NOWHERE READABLE. Eleven
targets, each with a paragraph in the Makefile saying why it is or is not on the commit path,
what toolchain it needs, and whether it writes — roughly 120 lines of comment spread through a
522-line file, none of it reachable without opening that file. `make help` carried the summary,
and the summary was WRONG: it said `harness + docs-audit + the self-tests + lint + typecheck`
while five more targets ran, and had said so since those five landed. CLAUDE.md caught up; the
front door never did, and nothing compared them.

So the composition becomes data with a reader. Three rows in `scripts/docs-audit.py` consume
this file — `check registry` reconciles it against the Makefile recipe, `check census`
reconciles the published prose against it, and `commit path writes` asserts D18 mechanically
for the first time by refusing any writing check on the commit path.

**THIS FILE DOES NOT DRIVE `make check` AND MUST NOT.** The Makefile recipe is what runs; this
is a parallel declaration reconciled against it. The distinction is the whole point of the
shape: a wrong entry here is an explainer that lies, which the audit catches, whereas a
registry that DROVE the suite could silently stop running a check — and a check that silently
stops running is the failure this repo has paid for more than any other.

`CHECKS` is a tuple of pure literals for the reason `docs/map.py` and `scripts/status.py`'s
`SOURCES` are: the audit parses it with `ast.literal_eval` rather than importing it, because a
read-only check must not execute the code it is checking.

Stdlib only, no venv, no network — `python3` and not `$(PYTHON)` in the Makefile, same as
`status` and `docs-audit`. A step-away tool that needs `make venv` first is not a step-away
tool.

    scripts/checks.py            the table
    scripts/checks.py <target>   one entry, in full
"""

from __future__ import annotations

import sys
from typing import Dict, List, Sequence

WIDTH = 78


# The `needs` vocabulary, declared rather than spelled freehand per entry. A token nobody
# defined is a token nobody can reason about, and the `check registry` row refuses one — so
# this dict is a reader for itself as well as the renderer's legend.
NEEDS = {
    "python3": "a bare system python3. No venv, no packages.",
    "venv": "`make venv` — the harness needs the anthropic SDK, Pillow and numpy.",
    "node": "node on PATH.",
    "app deps": "`npm --prefix app install` — gitignored, so it does not travel to a worktree.",
    "git": "git, and a repository.",
    "bash": "bash, not merely a POSIX sh.",
    "sh": "any POSIX sh.",
    "vale": "the vale binary — `brew install vale`. Absent, the target reports and exits 0.",
}


# One entry per target in the Makefile's `check:` recipe, in recipe order.
#
# `writes` IS A SENTENCE AND NOT A FLAG, and that is deliberate: "it writes" is the start of
# the question D18 asks, never the end of it. An empty string means it writes nothing anywhere.
# `commit path writes` in the audit reads it as truthy/falsy and reports the sentence, so the
# reason travels with the finding.
#
# `why_off_commit_path` is empty exactly where `commit_path` is true. The audit checks that
# pairing, because an entry claiming both would be describing nothing.
CHECKS = (
    {
        "target": "harness",
        "runs": "$(PYTHON) harness/run.py",
        "asserts": "Every verification test in harness/run.py's TESTS list. RECOUNT FROM THERE "
                   "— this entry deliberately carries no number, because a count published "
                   "beside a list is the drift this whole file exists about.",
        "needs": ("venv",),
        "writes": "harness/results/t1*.json, but only when the measurement itself changed — a "
                  "timestamp bump alone is not a change and is not written.",
        "commit_path": False,
        "why_off_commit_path": "It writes, and it needs the venv. D18 keeps a writing thing off "
                               "the path that decides whether a commit proceeds; the Stop hook "
                               "runs it at turn end instead.",
        "gates": True,
        "governed_by": ("D18",),
    },
    {
        "target": "docs-audit",
        "runs": "python3 scripts/docs-audit.py",
        "asserts": "Every reference in the markdown resolves against the code it names. Exit 1 "
                   "is provably wrong and blocks; exit 2 is the coupling question, printed and "
                   "allowed (D16).",
        "needs": ("python3",),
        "writes": "",
        "commit_path": True,
        "why_off_commit_path": "",
        "gates": True,
        "governed_by": ("D16", "D18"),
    },
    {
        "target": "audit-self-test",
        "runs": "python3 scripts/docs-audit.py --self-test",
        "asserts": "The auditor's own extractors, against fixtures it builds and destroys. It "
                   "sat red and unnoticed until 2026-08-24 because nothing ran it at all.",
        "needs": ("python3",),
        "writes": "a temporary directory it makes and removes.",
        "commit_path": False,
        "why_off_commit_path": "D18: `--self-test` is the one mode of docs-audit.py that "
                               "writes, and nothing that writes may run on the path that "
                               "decides whether a commit proceeds. `make check` is invoked by a "
                               "person, so it is not that path.",
        "gates": True,
        "governed_by": ("D16", "D18"),
    },
    {
        "target": "githooks-selftest",
        "runs": "bash scripts/githooks-selftest.sh",
        "asserts": "D42's two hooks over main, exercised in a bare repo and a clone built for "
                   "the run. A refusal must carry the hooks' own `REFUSED:` marker, so git's "
                   "own refusals cannot score as the guard's.",
        "needs": ("bash", "git"),
        "writes": "a bare repo, a clone, commits and pushes, all under `mktemp -d`.",
        "commit_path": False,
        "why_off_commit_path": "D18, and a second reason of its own: it exercises the guard by "
                               "VIOLATING it, so a version on the commit path would be refusing "
                               "its own commits.",
        "gates": True,
        "governed_by": ("D18", "D42"),
    },
    {
        "target": "port-agreement",
        "runs": "python3 scripts/port-agreement.py",
        "asserts": "server/ports.py and app/devPort.ts answer the same port for the same "
                   "checkout path. Two languages hold one algorithm and neither can import the "
                   "other; a disagreement is silent and total.",
        "needs": ("python3", "node"),
        "writes": "a temporary directory it makes and removes.",
        "commit_path": False,
        "why_off_commit_path": "It runs node, and the pre-commit hook runs a bare python3 with "
                               "nothing installed — a check needing a toolchain would fail on a "
                               "machine that has none rather than on a defect.",
        "gates": True,
        "governed_by": ("D18", "D43"),
    },
    {
        "target": "set-hint-agreement",
        "runs": "python3 scripts/set-hint-agreement.py",
        "asserts": "The capture screen and the export fetch resolve a set hint alike. The same "
                   "shape as port-agreement one decision over, and worse when it drifts: a "
                   "verdict shown at the rig gets trusted.",
        "needs": ("python3", "node"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "node again, so it is off the commit path for port-agreement's "
                               "reason: the git hook runs a bare python3.",
        "gates": True,
        "governed_by": ("D18", "D65", "D76"),
    },
    {
        "target": "screen-freshness",
        "runs": "node scripts/screen-freshness.mjs",
        "asserts": "Every server write in app/src has a way back — a re-read, an invalidation "
                   "signal, or a reason in the code why none is owed. It finds NOTHING today: "
                   "it guards write number 39, not a bug that exists.",
        "needs": ("node", "app deps"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "port-agreement's reason exactly — it runs node, and the git "
                               "hook runs bare.",
        "gates": True,
        "governed_by": ("D18",),
    },
    {
        "target": "ignore-check",
        "runs": "sh scripts/ignore-check.sh",
        "asserts": "Every path a worktree provisions is gitignored — as a file, as a directory "
                   "and as a symlink (D47).",
        "needs": ("sh", "git"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "D18, plus one of its own: it asks about local PROVISIONING, so "
                               "a fresh clone with none of these paths present would fail a "
                               "commit over nothing.",
        "gates": True,
        "governed_by": ("D18", "D47"),
    },
    {
        "target": "lint",
        "runs": "npm --prefix app run lint",
        "asserts": "eslint over app/, one rule per bug this project caught itself. JavaScript "
                   "only — Python has no linter here, and this target does not claim otherwise. "
                   "No `--fix`, here or in the npm script, per D18.",
        "needs": ("node", "app deps"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "It runs node, and the git hook runs a bare python3.",
        "gates": True,
        "governed_by": ("D18",),
    },
    {
        "target": "vale",
        "runs": "git ls-files '*.md' | xargs vale --no-exit",
        "asserts": "Prose style over every TRACKED markdown file (D74). IT NEVER GATES, twice "
                   "over: `--no-exit` swallows its findings' status, and a missing binary "
                   "reports and exits 0 so `make check` still runs on a machine without it.",
        "needs": ("vale",),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "vale is a third-party Go binary, and the pre-commit hook runs a "
                               "bare python3 (D18). A commit gate needing software PRESENT "
                               "would make the three opsec rules depend on it too.",
        "gates": False,
        "governed_by": ("D18", "D60", "D74"),
    },
    {
        "target": "typecheck",
        "runs": "npm --prefix app run typecheck",
        "asserts": "tsc --noEmit over app/.",
        "needs": ("node", "app deps"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "It runs node, and the git hook runs a bare python3.",
        "gates": True,
        "governed_by": ("D18",),
    },
)


# --------------------------------------------------------------------------- rendering


def wrap(text: str, indent: int, width: int = WIDTH) -> List[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) + indent > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def table() -> str:
    longest = max(len(entry["target"]) for entry in CHECKS)
    lines = [
        f"PKMNSCAN — what `make check` runs" + f"{len(CHECKS)} checks".rjust(
            WIDTH - len("PKMNSCAN — what `make check` runs")
        ),
        "=" * WIDTH,
        "",
        f"  {'target':<{longest}}  gates  commit  writes  needs",
        f"  {'-' * (WIDTH - 2)}",
    ]
    for entry in CHECKS:
        lines.append(
            "  {target:<{w}}  {gates:^5}  {commit:^6}  {writes:^6}  {needs}".format(
                w=longest,
                target=entry["target"],
                gates="yes" if entry["gates"] else "NO",
                commit="YES" if entry["commit_path"] else "no",
                writes="yes" if entry["writes"] else "-",
                needs=", ".join(entry["needs"]),
            )
        )
    lines += [
        "",
        "  gates   a finding here fails `make check`. `vale` deliberately does not.",
        "  commit  scripts/githooks/pre-commit runs it, so it decides whether a commit",
        "          proceeds. D18: nothing that WRITES may ever be in this column.",
        "",
        "  `make explain ARGS=<target>` for one entry in full.",
        "",
        "The Makefile's `check:` recipe is what actually runs; this file is a parallel",
        "declaration, and `make docs-audit`'s `check registry` row fails the commit that",
        "lets the two disagree.",
    ]
    return "\n".join(lines)


def one(name: str) -> str:
    entry = next((e for e in CHECKS if e["target"] == name), None)
    if entry is None:
        known = ", ".join(e["target"] for e in CHECKS)
        return f"no check called `{name}` runs in `make check`.\n  These do: {known}"

    lines = [f"make {entry['target']}", "=" * WIDTH, ""]

    def block(label: str, text: str) -> None:
        for i, line in enumerate(wrap(text, 14)):
            lines.append(f"  {label if i == 0 else '':<12}{line}")

    block("runs", entry["runs"])
    block("asserts", entry["asserts"])
    block("needs", "; ".join(f"{n} — {NEEDS[n]}" for n in entry["needs"]))
    block("writes", entry["writes"] or "nothing, anywhere.")
    if entry["commit_path"]:
        block("commit path", "YES — scripts/githooks/pre-commit runs this, so it decides "
                             "whether a commit proceeds.")
    else:
        block("commit path", "no.")
        block("", entry["why_off_commit_path"])
    block("gates", "a finding fails `make check`." if entry["gates"]
          else "NO — it reports and `make check` carries on.")
    block("governed by", ", ".join(entry["governed_by"]) + "  — docs/DECISIONS.md")
    return "\n".join(lines)


def main(argv: Sequence[str]) -> int:
    if argv:
        print(one(argv[0]))
        return 0 if any(e["target"] == argv[0] for e in CHECKS) else 1
    print(table())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
