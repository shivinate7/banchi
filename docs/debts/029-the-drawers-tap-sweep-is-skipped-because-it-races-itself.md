## 29 — The drawer's tap sweep is skipped, because it races itself on a slower runner

`app/tests/phone.spec.ts`'s `every drawer route is reachable by tap, at two phone heights` is
`test.skip` as of 2026-09-17, on the owner's word, as an explicitly TEMPORARY bandaid. The
subject is sound; the test's own timing is not.

**What was measured.** It failed three times on CI and never once on the rig. Shard 2 of 3,
twice on PR #375's head (7m54s, 7m40s) and again on that PR's claim commit; shards 1 and 3
passed every time; the full suite passed locally on the same tree, 633 of 634, the single
failure being an unrelated word-count pin. Every failure is identical:

    ✘ tests/phone.spec.ts:541:1 › every drawer route is reachable by tap, at two phone heights
    Error: page.goto: net::ERR_ABORTED; maybe frame was detached?

Three identical failures is not DEBTS §8's one-in-thirteen flake, and reading it as one is the
mistake this entry exists to prevent.

**The unconfirmed hypothesis.** The inner loop taps a drawer row, asserts the URL, then calls
`page.goto('/')` to set up the next row. The tap's own navigation may still be in flight when
that `goto` is issued, and the slower runner loses the race. NOBODY HAS CONFIRMED THIS. It is
written down as a hypothesis precisely so the next session tests it rather than inheriting it
as a finding — and a fix that merely passes locally proves nothing here, because the bug
already passes locally. Reproduce the failure first, under throttling or load, then fix.

**What is unguarded while it sleeps, and it is not small.** That every drawer row is reachable
by a thumb at 390 and 360, and that the drawer's foot does not cover a row's centre. That is
exactly the defect that left the Codes screen unreachable by touch and that this test was built
to catch. A phone-shaped regression in the drawer will now ship silently.

**What may not happen to it.** It may not be deleted, and it may not be "fixed" by a retry, a
`waitForTimeout`, a loosened assertion, or by narrowing what it sweeps — it discovers the
drawer's own rows rather than naming routes, and that property is the reason it caught anything.
`test.skip` rather than a deletion or a commented-out block is deliberate: `make design-check`
reports it as skipped on every run, so the gap announces itself instead of going quiet.
