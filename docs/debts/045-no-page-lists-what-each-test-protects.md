## 45 — no page lists what each test protects, so the owner cannot confirm the tests are current

**The finding.** On 2026-09-26 the owner asked where to view the whole list of tests. The
owner wants to confirm that each test is still current. No such view exists. The tests live
in three places, and each is written for a machine:

- `app/tests/*.spec.ts`: 44 files and about 1,071 browser tests, counted on main at `5b7f5d29`.
- `docs/gates/contract/`: one page per harness test, T1 to T11. T7 alone covers most of the
  store and the capture server.
- `scripts/*-selftest.py`: 32 guard self-tests.

`npx playwright test --list` prints the names. A name does not say which rule a test
protects, or whether that rule still stands.

**The want (owner, 2026-09-26, verbatim).** `yeah just save it as a deferred want add it to debts`.

**What would close it.** One page that states each test as one plain sentence, grouped by
screen. The sentence says what the test protects. At the top, the page flags two kinds of
test. The first kind cites a governing decision that was superseded. The second kind asserts
text or layout that the owner has since changed. A Sonnet agent reads the tests and writes
the page. The page is published privately for the owner.

**Why it is not done now.** The cost is about one agent's full session of reading. PR 4
changes several screens, so a page written now goes stale at once. Do it after PR 4 lands.
