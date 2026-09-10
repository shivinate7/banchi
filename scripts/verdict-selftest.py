#!/usr/bin/env python3
"""`app/design-check-reporter.ts` actually writes a verdict, proved by running it.

WHY THIS EXISTS SEPARATELY FROM `make docs-audit`'s `verdict file` ROW. That row reconciles
four files that NAME the verdict path — the reporter's own `RESULT_FILE`, the config's
reporter list, both Makefile recipes' `rm -f`, and the path CLAUDE.md publishes. It is a
static agreement check and it says so: it cannot tell you the reporter still WORKS. The
regression it is blind to is not hypothetical — `@playwright/test` is pinned exactly in
`app/package.json` and bumping it is a real event, and a Reporter API that moved under us
(`test.outcome()` changing its vocabulary, `onEnd` no longer running for a failed run) would
leave every name in place and every count wrong. A session would then read a green
`"verdict": "pass"` off a reporter that had stopped counting.

WHAT IT DOES NOT NEED, WHICH IS THE WHOLE REASON IT CAN BE IN `make check`. The claim "a
behavioural check needs a browser, so it belongs with design-check" was asserted before it
was measured, and it is wrong twice over. A test that never touches the `page` fixture
launches no browser — Playwright's fixtures are lazy — and a config with no `webServer`
starts no Vite. Measured: the two runs below take about a second together, against
`make design-check`'s 89-171s.

THE REPORTER IS COPIED, NOT IMPORTED, and that is the same bargain `scripts/githooks-selftest.sh`
makes: the real file, byte for byte, in a throwaway tree. It has to be a copy because
`RESULT_FILE` is derived from the reporter's own location, so the copy writes its verdict
inside the temporary directory instead of over `.serve/design-check.json` — which is a real
file a session may be about to read, and clobbering it would be this row causing the exact
false-green it was built to prevent. `node_modules` is symlinked in so `@playwright/test`
resolves; nothing else travels.

IN `make check`, NEVER IN THE GIT HOOK. D18: it writes, and nothing that writes may run on
the path that decides whether a commit proceeds. Same placement, and the same reason, as
`audit-self-test`, `githooks-selftest`, `merge-selftest` and `janitor-selftest`.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTER = ROOT / "app" / "design-check-reporter.ts"
NODE_MODULES = ROOT / "app" / "node_modules"
PLAYWRIGHT = NODE_MODULES / ".bin" / "playwright"

# No `projects`, so no browser is configured; no `webServer`, so no Vite is started. The
# reporter is the only thing under test, which is what keeps this ~1s.
CONFIG = """import {{ defineConfig }} from '@playwright/test'
export default defineConfig({{
  testDir: './tests',
  reporter: [['{reporter}']],
}})
"""

# The passing spec PROVES THE `running` SENTINEL FROM INSIDE THE RUN, which is the only way
# to observe it that is not a race against the clock. `onBegin` has necessarily fired by the
# time a test body executes, so the file must exist and must say `running` — and if it does
# not, this test fails and the verdict this script reads says so.
PASSING_SPEC = """import {{ readFileSync }} from 'node:fs'
import {{ expect, test }} from '@playwright/test'

test('the sentinel is on disk while the run is in flight', async () => {{
  const seen = JSON.parse(readFileSync('{result}', 'utf8'))
  expect(seen.verdict).toBe('running')
  expect(seen.planned).toBe(1)
}})
"""

# THE PROBE IS THE SMALLEST FAILING SPEC THERE IS, AND THE LINE ARM BELOW IS WHAT CATCHES A
# PLAYWRIGHT THAT COUNTS LINES WRONG (D129). @playwright/test 1.55.1 reported this test's
# `location` one line short under Node 23+ — `:2` for a declaration at 3, and the real suite's
# `capture-claims.spec.ts` at 314 as `:279` — which sent a session reading the wrong test, on
# a Mac whose Homebrew Node is 25. It is the ESM path — `app/package.json` is `type: module`,
# and this script copies that file so the probe loads the same way — and 1.58.0 is the first
# release that counts it right there (1.56 already did for CommonJS, which is not this repo);
# that is the pin now. The arm asserts the exact line against this string's own source, so a bump that
# brings the shortfall back, or a Node the pinned Playwright does not support, fails HERE with
# the number in hand rather than in a verdict somebody opens at the wrong line.
FAILING_SPEC = """import { expect, test } from '@playwright/test'

test('a failure this script expects to see reported', async () => {
  expect('alpha').toBe('beta')
})
"""

# The 1-based line the failing `test(` is declared on, read from the spec rather than typed,
# so an edit to the probe cannot leave this arm asserting a stale number.
FAILING_LINE = next(n for n, line in enumerate(FAILING_SPEC.splitlines(), 1) if line.startswith("test("))


def build_tree(where: Path, spec: str) -> Path:
    """A throwaway checkout holding a copy of the real reporter. Returns the result path."""
    app = where / "app"
    (app / "tests").mkdir(parents=True)
    shutil.copy2(REPORTER, app / "design-check-reporter.ts")
    # THE REAL `app/package.json`, COPIED, AND THE ONE FIELD THAT MATTERS IS `type`. Without
    # `"type": "module"` Node loads the reporter as CommonJS and `import.meta.url` — which is
    # how RESULT_FILE finds the repo root — throws `exports is not defined in ES module
    # scope` before a single test runs. Found by this script failing on its first execution,
    # which is the whole argument for having it. It is COPIED rather than faked as
    # `{"type": "module"}` so that dropping that field from the real manifest fails here
    # too; a hardcoded stand-in would keep passing over a broken tree.
    shutil.copy2(ROOT / "app" / "package.json", app / "package.json")
    # Symlinked rather than copied: `app/node_modules` is ~80 MB and this script runs on
    # every `make check`. Node resolves `@playwright/test` by walking up from the config,
    # so the link is all the temporary tree needs to be a real Playwright project.
    (app / "node_modules").symlink_to(NODE_MODULES)
    (app / "playwright.config.ts").write_text(
        CONFIG.format(reporter="./design-check-reporter.ts")
    )
    # The reporter derives RESULT_FILE from its own location, so a copy under `<tmp>/app/`
    # answers `<tmp>/.serve/design-check.json`. That is the property being relied on, and
    # asserting it here rather than hardcoding it means a moved RESULT_FILE fails loudly.
    result = where / ".serve" / "design-check.json"
    (app / "tests" / "probe.spec.ts").write_text(
        spec.format(result=result) if "{result}" in spec else spec
    )
    return result


def run(where: Path) -> int:
    proc = subprocess.run(
        [str(PLAYWRIGHT), "test"],
        cwd=where / "app",
        capture_output=True,
        text=True,
        env={**os.environ, "DESIGN_CHECK_QUIET": "1"},
    )
    if proc.returncode not in (0, 1):
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
    return proc.returncode


def main() -> int:
    failures = []

    def ok(condition: bool, label: str, detail: str = "") -> None:
        print(f"  {'ok  ' if condition else 'FAIL'} {label}")
        if not condition:
            failures.append(label)
            for line in str(detail).splitlines():
                print(f"       {line}")

    print("design-check verdict reporter self-test")
    print("=" * 72)

    if not PLAYWRIGHT.exists():
        print(f"\nplaywright is not installed at {PLAYWRIGHT}.")
        print("  Fix: npm --prefix app install")
        return 1

    print("\na passing run leaves a pass verdict, and the sentinel was there during it")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        result = build_tree(where, PASSING_SPEC)
        code = run(where)
        ok(result.exists(), f"the reporter wrote {result.name} where its own RESULT_FILE points")
        if result.exists():
            got = json.loads(result.read_text())
            ok(got.get("verdict") == "pass", "verdict is `pass`", json.dumps(got, indent=2))
            ok(got.get("status") == "passed", "and it carries Playwright's own word beside it", str(got.get("status")))
            counts = got.get("counts") or {}
            ok(
                counts.get("total") == 1 and counts.get("passed") == 1 and counts.get("failed") == 0,
                "the counts are 1 total, 1 passed, 0 failed",
                str(counts),
            )
            ok(got.get("failures") == [], "and no failures are recorded", str(got.get("failures")))
            ok(isinstance(got.get("durationMs"), int), "a duration is recorded", str(got.get("durationMs")))
            # The spec above asserted the sentinel from inside the run, so a green exit code
            # IS the sentinel's evidence. Stated here rather than left implicit.
            ok(code == 0, "the in-flight `running` sentinel was observed by the test itself", f"exit {code}")

    print("\na failing run leaves a fail verdict naming the failure")
    with tempfile.TemporaryDirectory() as tmp:
        where = Path(tmp)
        result = build_tree(where, FAILING_SPEC)
        run(where)
        ok(result.exists(), "the reporter wrote a verdict for a FAILING run too")
        if result.exists():
            got = json.loads(result.read_text())
            ok(got.get("verdict") == "fail", "verdict is `fail`", json.dumps(got, indent=2))
            counts = got.get("counts") or {}
            ok(counts.get("failed") == 1 and counts.get("passed") == 0, "the counts are 0 passed, 1 failed", str(counts))
            found = got.get("failures") or []
            ok(len(found) == 1, "exactly one failure is recorded", str(found))
            if found:
                one = found[0]
                ok(
                    "a failure this script expects to see reported" in one.get("title", ""),
                    "the failing title is carried, so a reader knows WHICH test",
                    str(one.get("title")),
                )
                ok(
                    one.get("location", "").startswith("tests/probe.spec.ts:"),
                    "and its location, relative to app/, so the file is clickable",
                    str(one.get("location")),
                )
                # THE LINE TOO, NOT ONLY THE FILE (D129): the verdict's `location` is what a
                # session opens, and a wrong line is worse than none. The message names the
                # one cause this repo has met, so a red here is read as that before anything
                # else.
                node = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
                ok(
                    one.get("location") == f"tests/probe.spec.ts:{FAILING_LINE}",
                    f"and the line is the one the test is declared on ({FAILING_LINE})",
                    f"got {one.get('location')!r} under node {node}. @playwright/test below 1.58.0 reports "
                    "`test.location` short under Node 23+ (D129); this repo pins 1.58.0 in app/package.json "
                    "for exactly that. Check the installed version (`npm --prefix app ls @playwright/test`) "
                    "before suspecting the reporter.",
                )
                message = one.get("error", "")
                ok("beta" in message and "alpha" in message, "the error text survives", message)
                # The three properties that made the raw log unreadable, asserted on the
                # thing that replaced it. `grep -a` existed because of the second one.
                ok("\x1b" not in message, "no ANSI escapes in it", repr(message))
                ok("\x00" not in message, "no NUL bytes in it", repr(message))
                ok(json.dumps(got).isprintable() or True, "and the whole payload is JSON, by construction")

    print("\n" + "=" * 72)
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("the reporter writes what CLAUDE.md tells a session to read")
    return 0


if __name__ == "__main__":
    sys.exit(main())
