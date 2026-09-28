## DEBT51 — A guard or probe can pass for the wrong reason

Drafted from the 2026-09-27 memory migration. A catalog of shapes. Each produced a
confident wrong "green" in this repo. Kept together because the failure mode repeats, across
very different tools. Item 12 below is `dry-run-blocklists-fail-open` (the memory entry of
that name) — `docs/specs/verification-cost.md` §6B cites this failure by that name.

1. **The fixture never drew the control under test.** A case guarded on `if (await
   bar.count())`. The seeded store never loaded a run that would render the bar at all. The
   assertion inside never ran. The case still reported green.
2. **The probe only measured the fold.** `elementFromPoint` answers about the current
   viewport alone. A sweep that never scrolls tests only the first screenful, of a page that
   runs to 13,000px.
3. **The client under the assertion discards the evidence.** `http.client` already zeroes a
   HEAD response's read length, before a byte is read. So `checks.equal(body, b"")` passed
   against a server mutated to write a full body on HEAD. The library between the assertion
   and the wire answered the question by itself. Read raw bytes off the socket instead, when
   the assertion is genuinely about what went out on the wire.
4. **A restarting counter, or a hand-written literal in a fixture, survives the exact
   mutation an arm exists to catch.** Build a decoy in a regression arm with the SAME
   generating function the real code uses. Never a typed-in value.
5. **A per-run fixture races a MACHINE-WIDE resource it treats as private.** One example: a
   fixed process name, resolved through a global `pgrep -f`. Another: a "free" port, found by
   probing a range instead of binding port 0. On a machine running many concurrent
   worktrees, another session's identically-named process — or the same probed port — makes
   the guard correctly refuse. That reddens the one arm that must never fail. The fix makes
   collision impossible: a `<role>-<mktemp>-<pid>` name, a kernel-assigned port read back. It
   never adds a lock. Fixtures never "take turns" either — that would block one tree's suite
   on another's unrelated commit. `pgrep -fc` is not a count, on BSD. It returns 0 and reads
   as "no orphans." Count with `pgrep -f ... | wc -l` instead.
6. **A citation-checking probe that tokenizes the citation itself scores a hit off the
   subject's own filename.** A citation naming a pipeline module by path and line yields the
   token "join." That token then "verifies" against almost any line of that same module. Exclude every token derived
   from the subject's own path and stem, before matching. Count "names no real identifier" as
   NOT CHECKABLE, never as a pass. Measured here: 38% of one corpus's "hits" were this
   artifact alone.
7. **A Playwright geometry sweep, green locally and red on CI, is usually a sampling
   artifact.** It is rarely a real defect. Scan every whole-pixel scroll offset instead of
   reaching for CSS. Say it passes at most offsets, with one consecutive failing band. That
   means that a sticky or fixed ancestor covers the control. This happens at one exact scroll
   stop, on the runner's own font metrics. Passing at zero offsets is the real,
   scroll-invariant case. A sweep that steps in large viewport fractions can sample a long
   page at only two points. A wide failing band can then misread as a knife-edge flake. It is
   the opposite: more fragile, not less.
8. **Reading a retained Playwright trace by its request timeline alone upgrades a theory to
   an unearned certainty.** Decode the actual fulfilled response bodies first. They live in
   the trace's `test.trace` JSONL, as `before` events. Playwright's own array-failure output
   is a DIFF, never a positional list. A `-` line is expected-only. A `+` line is
   received-only. The two are aligned between each other. Three sessions here misread it as
   positional. Each chased a bug that did not exist.
9. **A test that mutates its own stub AFTER a `click()` races the browser.** `click()`
   resolves on dispatch. It never waits for the app's own re-read to complete. The shape only
   sometimes produces a wrong answer, so no static check can flag it. Move the mutation into
   the WRITE route's own handler instead. Order it after the row's fetch, before the re-read.
   Moving it earlier than the press breaks the case a different way. `await
   page.waitForTimeout(300)`, between the click and the mutation, turns a latent race into a
   deterministic red — for diagnosis only. Never commit it.
10. **Four mutation arms can all go green over one row, for three unrelated reasons at
    once.** It may be the walk's current row. Or this screen just sold it. Or the ranking is
    frozen by it. A case aimed at the fold or the freeze alone must act on a MID-list row.
    That row must be none of those three. Otherwise every arm proves the same easy reason,
    regardless of what the code under test does.
11. **A mutation run owns the whole working tree for its duration.** A `git stash`, even of
    an unrelated file, fired mid-run once. It let a background Playwright run restore a
    mutated file. That run then reported a false PASS — the same dev server serves the whole
    `app/src`. Never commit, stash, check out, or edit anything, while a mutation run is in
    flight.
12. **A dry-run guard, built from a deny-list of guessed endpoint names, fails OPEN.**
    Blocking POSTs by function names, read out of a bundle's JavaScript, let a real 100-row
    TCGplayer Staged import through. The real wire endpoint names matched no guessed name.
    The guard logged nothing. For any dry run against a live account: invert it. Block every
    non-GET by default. Allow only calls already observed and judged safe. Verify the guard
    actually fires, by driving one harmless write through it first.
13. **`make check` measured red at `reap-selftest`, on `origin/main` itself, on
    2026-09-12.** Standalone, the same target passed 31/31, on the same tree. Nobody
    re-verified this after that date. Before assuming a red `check` in this lane is your own
    fault, run the same target set on a detached checkout of `origin/main`. `check` stops at
    the first failure. `reap-selftest` sits 11th of the aggregate. A red there silently skips
    `lint`, `typecheck`, and everything after it.
