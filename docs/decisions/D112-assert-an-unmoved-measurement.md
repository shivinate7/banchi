## D112 — Assert an unmoved measurement

**T1 asserts that its inputs are unmoved and does not re-run the model.** Between two turns it can learn nothing: the model is pinned, the responses are banked in `harness/.cache`, the labels are fixed and the floor is a constant. Only three things can move, and each has a fingerprint: the prompt, the eval set, and the arithmetic (`scorer_fingerprint()` hashes the per-card comparison, per-set aggregation, holdout split and floor, as function source and not the module, so a comment edit never demands a paid measurement).

- **The ordinary path compares three hashes against what `harness/results/t1.json` was generated under,** and holds the committed holdout to its floor. Four named checks, 3 ms. A mismatch falls through to the replay, which is where the images and the money are. A re-measurement needs an explicit flag and a key.
- **Labels are tracked and images are not.** `EvalCard` is ground truth except `image`, which is a filename. The labels were untracked only because they sat inside gitignored `harness/images/`. They live in `harness/eval/manifest.json` now. The old location is still read and never written. T1 therefore runs in a fresh clone, an unprovisioned worktree and CI, and the harness is hermetic, so `make ci-check` runs it.
- **`generated_at` names the run that produced the score.** Adding a field is not a re-measurement.
- **T1 stays in the Stop hook,** since at 3 ms a prompt edit is caught at the end of the turn that made it.

It retires when the inputs stop being frozen (a floating model or a regenerating eval set).
