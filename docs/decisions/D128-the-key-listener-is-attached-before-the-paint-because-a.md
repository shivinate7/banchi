## D128 — The key listener is attached before the paint, because a press answers to what is on the screen and not to the render before it

**Settled 2026-09-10, on the owner's instruction to find the recurring one-test red on**
**`make design-check` in CI and fix it only if the evidence supported one.** The hypothesis handed
in was D122's: a starved runner reproducing the 2026-09-07 collapse with no lock to protect it.
**It did not hold, on three counts**, and the measurement is what this entry exists to keep.

### What was measured

**Sixteen completed `design-check` jobs since the job landed on 2026-09-08; three failed, never**
**more than one test each — about one run in five.** The runner reports `Running 462 tests using 1
worker`: Playwright's default under `CI` is one worker, so the runner executes this suite in the
LEAST parallel configuration it has ever run in. 803–1058 seconds is 462 tests in series on a
four-core box, not contention. **Failure did not track wall-clock**: the fastest run (783s) passed,
the slowest (1058s) passed, the three failures sat between at 827, 846 and 951. And the casualty
was not random across the suite: **twenty of 462 tests go through `capture-claims.spec.ts`'s**
**`open()` helper, and they took two of the three.**

**Every recorded casualty was one defect.** The five instances — `capture-claims.spec.ts:314` and
`:816`, `live-reconcile.spec.ts:236`, `markdown.spec.ts:539` twice (once on PR #230, rerun green,
and once in the first run of the job) — each fail at the assertion immediately after a
`keyboard.press('Escape')` that follows an assertion about the painted DOM. Two shapes, one cause:
the capture screen's Finish track stays open under an Escape meant to close it (`toHaveCount(0)`
polled 19 times at 3), and the reconcile and markdown sheets CLOSE under an Escape meant to be
held while a request is in flight (`toBeVisible` on a dialog that is gone).

### The mechanism

`app/src/runsOverlay.ts:useOverlayFocus` and `app/src/CaptureScreen.tsx`'s field handler both
registered a window `keydown` listener in a `useEffect` whose dependencies include the state the
handler reads — `hold` in one, `openField` in the other, and `fieldPick` closes over `openField`
too. **A passive effect runs after the browser paints.** So for one task, the screen shows the
drop zone `disabled` (or the track open) while the listener still attached is the previous
render's, whose closure says `hold === false` (or `openField === null`). A press dispatched into
that task is not queued behind the re-registration; it is answered by the wrong render — the
sheet closes mid-request, the Escape finds no field to close and returns. `capture-claims.spec.ts`
had already met the first-mount version of this and retries its `F` for it, in a comment that
names the exact phenomenon; its Escape was pressed once.

**It is invisible on the rig because Playwright's round trip is longer than the effect flush there.**
On the runner the flush is slower than the round trip often enough to show once a run.
**Reproduced deterministically without loading anyone's machine**: `Emulation.setCPUThrottlingRate`
at 10x, one worker, the four affected cases five times each — **3 of 20 failed** on the tree as
merged, all three the held-sheet shape, at the same lines CI reported.

### The ruling

**Both listeners are registered in `useLayoutEffect`.** A layout effect runs inside the commit,
after the DOM is mutated and before the browser paints, and the commit is synchronous — no
evaluation from a test and no input from a person can interleave with it. So a state the screen
shows is a state the listener already has. **The same four cases, same throttle, same repeats:**
**20 of 20.**

**It is a product fix and not a test fix, because the held sheet's window is real for a person.**
`useOverlayFocus`'s hold exists so that a stray Escape cannot close a sheet whose request would
then toast for a sheet that is gone (D87, D100), and the window where it failed opens at the
exact moment the request starts — which is when somebody who just pressed the button is most
likely to press Escape. A retry in the spec would have made the test true and left that. The
capture screen's version is narrower for a human — a press within one frame of the previous one
— but it is the same code shape, and the fix is the same word.

### What was refused, and why each would have been read as weakening

- **`retries: 1` on CI.** It would have reclassified these as `flaky` and kept the count, and the
  count was the evidence: every one of the five would have been retried past the defect this
  entry names. Playwright's standard answer is right for an environment fault and this was not
  one.
- **A longer `expect` timeout.** The Escape was lost, not slow: `toHaveCount(0)` resolved to 3
  nineteen times over fifteen seconds. No wait answers a press that was answered wrongly.
- **Fewer or more workers.** There is one. There was nothing to tune.
- **A retry loop around the Escape in the spec**, symmetric with the `F` retry above it. It
  weakens nothing and would have made both specs pass, and it leaves the held sheet closable by a
  person. The `F` retry stays, because its cause — no listener on first mount before the first
  passive effect — is a different window this ruling does not close, and the retry is over the
  test's timing rather than the screen's behavior.

### What this does not do

**It does not touch D122.** That lock is about two fleets on one Mac and the measurement behind it
is untouched; the runner is one fleet on one box, which the workflow already says. **It does not**
**change what the suite asserts** — no floor moved, no timeout moved, no assertion was made
conditional. **It does not promise a green CI**: the 1-in-462-on-CI flake rate in
`app/playwright.config.ts`'s own first-visibility account is a different window and the memory of
this repo records the runner's chromium as a separate platform for a reason (D118, amended).
What it removes is the one class every recorded casualty belonged to.
