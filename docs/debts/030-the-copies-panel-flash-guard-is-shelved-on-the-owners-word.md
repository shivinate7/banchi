## 30 — The copies panel flash guard is shelved, on the owner's own word

Two tests in `app/tests/inventory.spec.ts` are `test.skip`, found by title. They are `the copies list holds while a new answer moves the walk to another drawer` and `a press to another drawer dims`. Both use `expectCopiesHeld`, which samples every animation frame during a delayed box fetch and asserts no frame lost the copies panel's rows. The owner disabled the guard, and it stays disabled until the owner says otherwise.

The guard caught this defect. During a delayed `GET /inventory/<box>`, a search-driven re-rank moves the walk from box 7 to box 2. For about 230ms (14 frames) the panel's rows blank to skeletons. The panel recovers, so only frame sampling sees it (D118's stability floor). The two tests failed 6 of 10 runs on main.

**Outcome at risk.** A skeleton flash in the copies panel on `#/inventory` ships unseen, on a fresh search answer or a direct press to another drawer.

**Closes when.** The panel stops blanking its rows while a fetch is in flight (a data-flow change in `BoxBrowse.tsx` or `Inventory.tsx`), or the owner accepts a new assertion as catching the same defect. Never a loosened assertion or a longer timeout.
