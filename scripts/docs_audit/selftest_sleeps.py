"""Self-test cases, the fixed sleeps row. Called by `selftest.self_test`.

The row goes red on a planted bare sleep and stays green on a kept one, a comment and a listed file.
"""

from __future__ import annotations

from .sleeps import bare_sleeps, sleep_findings

_BARE = "test('x', async ({ page }) => {\n  await page.waitForTimeout(300)\n})\n"


def run(ok) -> None:
    print("\nthe fixed sleeps row goes red on a planted bare sleep and stays green on a reasoned one")

    ok(bare_sleeps(_BARE) == [2], "a bare `page.waitForTimeout(300)` is found", str(bare_sleeps(_BARE)))
    ok(not bare_sleeps("  await page.waitForTimeout(300) // keep: asserts no write over 300ms\n"), "a same-line `keep:` reason passes", "")
    ok(not bare_sleeps("  // keep: asserts no write\n  await page.waitForTimeout(300)\n"), "a `keep:` reason on the line above passes", "")
    ok(bare_sleeps("  await page.waitForTimeout(300) // keep:\n") == [1], "an empty reason is still bare", "")
    ok(bare_sleeps("  await fulfiller.waitForTimeout(300)\n") == [1], "a sleep on another page object is found", "")
    ok(not bare_sleeps("// a `waitForTimeout(30)` is a floor\n * page.waitForTimeout(30) would flake\n"), "a comment naming the call is not a sleep", "")

    listed = {"a.ts": {"file": "a.ts", "count": 1, "reason": "helper"}}
    ok(not sleep_findings({"a.ts": [4]}, listed, listed, "allow.json"), "a listed file at its count is clean", "")
    ok(len(sleep_findings({"a.ts": [4, 9]}, listed, listed, "allow.json")) == 1, "a second bare sleep in a listed file is found", "")
    ok(len(sleep_findings({"b.ts": [2]}, listed, None, "allow.json")) >= 1, "a bare sleep in an unlisted file is found", "")
    ok(any("Lower the count" in f.message for f in sleep_findings({}, listed, listed, "allow.json")), "a listed count the file no longer holds is stale", "")
    ok(any("only shrinks" in f.message for f in sleep_findings({"a.ts": [4]}, listed, {}, "allow.json")), "a count above the merge-base's is growth", "")
    ok(any("no reason" in f.message for f in sleep_findings({"a.ts": [4]}, {"a.ts": {"file": "a.ts", "count": 1}}, None, "allow.json")), "an entry with no reason is found", "")
