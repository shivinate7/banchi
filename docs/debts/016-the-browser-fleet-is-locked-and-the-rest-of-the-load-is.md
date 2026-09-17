## 16 — The browser fleet is locked and the rest of the load is not, and only one of those was measured

D122 puts `make design-check` behind a machine-wide `flock` so two checkouts cannot run Playwright
fleets at once. **That decision is measured; the scope of it is partly reasoned**, and this section
is the difference between the two so no later session takes a green `make check` for coverage of
concurrency it never looked at.

**WHAT WAS MEASURED.** 2026-09-07, `magical-kalam-0230c3` against `cap-on-demand`: two fleets, ~90
browser processes on a 15-core Mac, 18 failures all in `shipping.spec.ts` and `run-panel.spec.ts`,
52 passing on a re-run with nothing touched, and two earlier single-spec flakes from the same
collision. `app/playwright.config.ts` carries the within-one-run version of the same finding at 40
workers against 12 CPU hogs. Section 11 above carries the capture server's version of it.

**WHAT WAS REASONED.** That `make harness` and `make check` do not need the lock.

- **`make harness` is nine tests in one Python process, and it runs at every turn end from the
  Stop hook.** The second half is the real argument: a lock refusal there is a false failure at
  the moment a session is trying to finish — the exact thing D122 exists to prevent — and two
  sessions ending a turn at the same moment is not rare, it is Tuesday.
- **`make check` shells out to `tsc`, `eslint` and `ruff`.** Two concurrent runs is a handful of
  mostly single-core processes against fifteen cores, an order of magnitude off the load that
  produced the eighteen failures. **Nobody has run two at once and counted**, and that is the
  honest state of it. If a session ever sees `make check` fail in a way a re-run clears, this is
  the paragraph to come back to.

**WHAT THE LOCK CANNOT SEE, and none of it is fixable from inside this repo:**

- **A hand-rolled Playwright script.** `npx playwright test` from a shell, a `page.goto` from a
  scratch file, the Browser pane driving the app — none of it goes through the Makefile, so none
  of it takes the lock. Section 11 records a session that did exactly this while also running
  `make design-check` eight times, and it is what wedged the owner's capture server. The lock
  narrows the window; it does not close it.
- **A checkout whose branch predates the lock.** The guard is a line in the `Makefile`, so a
  worktree cut before D122 landed runs the fleet without taking anything, and the tree that
  DOES take it is refused by nobody. Observed within the hour this was written: a session in
  `card-inventory-before-after-935912` started `make design-check` off an older branch while
  this one held the lock free. Nothing can fix that from here — every guard this repo installs
  by copy has the same property (`make hooks`, `make janitor-install`), and it resolves itself
  as branches merge. What it means in practice: for the first few days the lock is a courtesy
  between up-to-date trees rather than an exclusion across all of them.
- **Anything else on the machine.** A build, a video call, an `npm install`, a compile in
  somebody's editor. The lock
  serialises this repo against itself and claims nothing about the rest of the Mac.
- **A second user, or a second machine over a shared filesystem.** The lock lives under `~`,
  which is where the contention is for a single-operator rig and is wrong the moment that stops
  being true.
- **`make screenshot`.** Argued out of scope in D122 rather than overlooked: it renders one page
  at a time — a serial loop over the manifest, one `chromium.launch()` per view — and queueing a
  single render behind a ten-minute suite buys nothing measured. A render taken during a fleet run
  is slower, not wrong. (D122 named `playwright screenshot` here for a day; #223 had replaced that
  CLI with `scripts/screenshot.mjs` hours earlier. The shape is what the exclusion rests on, so
  the shape is what both documents say now.)

**WHAT WOULD MAKE THIS SECTION SHORTER.** A measurement — two `make check`s side by side, timed
and diffed for failures that are not in the code. It costs one session and would replace the
second bullet above with a number in either direction. Nothing is blocked on it.
