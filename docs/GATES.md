# Harness contract and build order

**THIS FILE IS A POINTER.** The records are in `docs/gates/`, one file each. Gating is retired
(2026-08-23): no gate is current and no step is blocked behind one. The Gate A, B and C run
records were deleted, and history lives in version control.

Two kinds of record are live:

- **`docs/gates/contract/`** — the harness's own thresholds, `T1` to `T9` and `T11`. Each is cited
  elsewhere as a bare `Tn`. `PASS_CRITERIA` in `harness/tests/*.py` is the ground truth, and a
  `### Tn` file here publishes it. `make docs-audit`'s `pass criteria` row reconciles the two.
- **`docs/gates/steps/`** — the build order. `docs/map.py`'s `SHIPPED` and `OPEN` carry the same
  ids, and `build order mirror` checks both directions. `n` is a stable id and is never
  renumbered. `SHIPPED` is ordered by landing date. `OPEN` is unordered and has no `next`.

`docs/gates/ORDER.json` is the manifest. Its `order` is the exact reassembly order, and its
`tests` and `steps` fields are the two indexes. `scripts/gates_corpus.py` reads it, and
`make gates-selftest` proves the set is complete.
