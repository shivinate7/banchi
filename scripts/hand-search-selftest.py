#!/usr/bin/env python3
"""`make hand-search-selftest` — proves `app/eslint.config.js`'s `HAND_SEARCH_RULES` sees the
shape it is for, red on a hand-rolled search and green everywhere else.

WHY THIS EXISTS (F11c, the reviewer's own finding on lane F11b). The round-one rule matched
one shape only, `x.toLowerCase().includes(y)`. It let three real shapes through silently:
`.startsWith`/`.endsWith`/`.indexOf` beside `.includes`, `.toLocaleLowerCase()` beside
`.toLowerCase()`, and a fold on the ARGUMENT instead of the receiver
(`x.includes(y.toLowerCase())`). A rule proved on one shape and silently missing three more is
worse than an honest gap: `docs/decisions/D271-one-forgiving-search-matcher.md` said "every
search field," and a reviewer had to read the selector itself to find out it did not.

THE ONLY WAY TO PROVE AN ESLINT SELECTOR IS THE SELECTOR ITSELF, RUN. Reading
`app/eslint.config.js`'s esquery string and reasoning about what it matches is exactly the
mistake that shipped the narrow rule in the first place. This script shells out to the real
`npx eslint --stdin`, over a tiny fixture per shape, the same "run the checker on fixtures in
both directions" method `css-var-check.py --self-test` and `make kit-adoption-selftest` use.
`--stdin-filename` decides which config block applies: `src/fixture.ts` gets
`HAND_SEARCH_RULES`, `tests/fixture.spec.ts` does not (the tests/-exemption block).

NOT ON THE GUARD-SCOPE ROSTER, ARGUED. `scripts/guard-scope.py:derive_subjects` reads a
self-test's own Python imports and `Path`-style chains to find its real subject, which is how
every other guard self-test earns a place on that roster without a hand-typed dependency list.
This script's real subject is `app/eslint.config.js`, a JS file no Python import statement can
name — there is no import chain here for `derive_subjects` to read, only a shelled-out `npx
eslint` invocation, and adding a subject by hand would defeat the roster's own point (D247):
subjects are derived from the test's source, never typed beside it. `css-var-check-selftest`
and `kit-adoption-selftest` are not on the roster for the identical reason. Wired into
`make check` ungated instead, the same place those two sit.

Exit 0 on every case passing, 1 otherwise.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"

Case = Tuple[str, str, str, bool]
# (name, stdin filename (relative to app/), snippet, expect a HAND_SEARCH finding)

CASES: Tuple[Case, ...] = (
    # ---- one shape per method, receiver-folded: `x.<fold>().<method>(y)` -----------------
    (
        "includes, receiver folded with toLowerCase, is a finding",
        "src/fixture.ts",
        "export const r = a.toLowerCase().includes(b)\n",
        True,
    ),
    (
        "includes, bare, no fold on either side, is not a finding",
        "src/fixture.ts",
        "export const r = a.includes(b)\n",
        False,
    ),
    (
        "startsWith, receiver folded with toLocaleLowerCase, is a finding",
        "src/fixture.ts",
        "export const r = a.toLocaleLowerCase().startsWith(b)\n",
        True,
    ),
    (
        # match.ts's own real shape (`raw.startsWith('/')`) must stay green: a bare
        # startsWith with no fold anywhere is an ordinary prefix test, not a search.
        "startsWith, bare, is not a finding (match.ts's own real shape)",
        "src/fixture.ts",
        "export const r = raw.startsWith('/')\n",
        False,
    ),
    (
        "endsWith, receiver folded with toLowerCase, is a finding",
        "src/fixture.ts",
        "export const r = a.toLowerCase().endsWith(b)\n",
        True,
    ),
    (
        "endsWith, bare, is not a finding",
        "src/fixture.ts",
        "export const r = a.endsWith(b)\n",
        False,
    ),
    (
        "indexOf, receiver folded with toLowerCase, is a finding",
        "src/fixture.ts",
        "export const r = a.toLowerCase().indexOf(b)\n",
        True,
    ),
    (
        "indexOf, bare, is not a finding (an ordinary array offset)",
        "src/fixture.ts",
        "export const r = list.indexOf(b)\n",
        False,
    ),
    # ---- the fold on the ARGUMENT instead of the receiver ---------------------------------
    (
        "includes, argument folded with toLowerCase, is a finding",
        "src/fixture.ts",
        "export const r = a.includes(b.toLowerCase())\n",
        True,
    ),
    (
        "startsWith, argument folded with toLocaleLowerCase, is a finding",
        "src/fixture.ts",
        "export const r = a.startsWith(b.toLocaleLowerCase())\n",
        True,
    ),
    # ---- an argued exemption still silences a real hit -------------------------------------
    (
        "an eslint-disable-next-line comment silences a real hit",
        "src/fixture.ts",
        "// eslint-disable-next-line no-restricted-syntax -- fixed word, not a typed query.\n"
        "export const r = a.toLowerCase().includes('foil')\n",
        False,
    ),
    # ---- the rule does not reach tests/ at all ----------------------------------------------
    (
        "the same finding, under tests/, is not a finding (the tests/ exemption block)",
        "tests/fixture.spec.ts",
        "export const r = a.toLowerCase().includes(b)\n",
        False,
    ),
)


def run_eslint(stdin_filename: str, snippet: str) -> int:
    """Runs the real `npx eslint --stdin` over one snippet, cwd `app/`. Returns the finding
    count `no-restricted-syntax` alone raised — any OTHER rule's own finding on a fixture this
    small would be a fixture bug, not a HAND_SEARCH one, so this counts by ruleId rather than
    trusting the process exit code, which any lint error trips."""
    result = subprocess.run(
        ["npx", "eslint", "--stdin", "--stdin-filename", stdin_filename, "--format", "json"],
        cwd=str(APP),
        input=snippet,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip() == "":
        print(f"    eslint produced no output (stderr: {result.stderr.strip()})")
        return -1
    payload = json.loads(result.stdout)
    messages = payload[0]["messages"] if payload else []
    return sum(1 for m in messages if m.get("ruleId") == "no-restricted-syntax")


def self_test() -> int:
    bad = 0
    for name, filename, snippet, expect_finding in CASES:
        count = run_eslint(filename, snippet)
        got_finding = count > 0
        ok = got_finding == expect_finding
        bad += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}: expected finding={expect_finding}, got {count}")
        if not ok:
            print(f"          snippet: {snippet.strip()!r} (as {filename})")
    print()
    if bad:
        print(f"hand-search-selftest: {bad} of {len(CASES)} cases FAILED")
        return 1
    print(f"hand-search-selftest: {len(CASES)} cases pass")
    return 0


def main(argv: List[str]) -> int:
    del argv
    return self_test()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
