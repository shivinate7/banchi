## 16 — The browser fleet is locked and the rest of the load is not, and only one of those was measured

D122 puts `make design-check` behind a machine-wide `flock`. Measured: two fleets (about 90 browser processes on a 15-core Mac) failed 18 cases in `shipping.spec.ts` and `run-panel.spec.ts`, and all passed on a rerun with nothing touched.

Reasoned and not measured: `make harness` and `make check` need no lock. `make check` shells out to `tsc`, `eslint` and `ruff`, so two at once is a handful of single-core processes, an order of magnitude under the fleet load. Nobody has run two side by side and counted.

The lock cannot see:

- a hand-rolled Playwright script or the Browser pane, which never go through the Makefile;
- a checkout whose Makefile predates the lock;
- anything else on the machine, such as a build, a video call or `npm install`;
- a second user or a second machine over a shared filesystem, since the lock lives under `~`;
- `make screenshot`, out of scope in D122 because it renders one page at a time.

**Outcome at risk.** A red that a rerun clears is read as a code defect, or a wedged capture server is blamed on the wrong load.

**Closes when.** Two `make check` runs side by side, timed and diffed for failures that are not in the code.
