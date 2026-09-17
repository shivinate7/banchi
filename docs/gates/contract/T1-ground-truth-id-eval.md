### T1 — Ground-truth ID eval

Download ~150 official card images from pokemontcg.io across at least 3 sets as labeled
fixtures (the API record IS the label). Run identification against them. Report accuracy
per set and overall.

- **Pass**: `holdout_accuracy >= 0.95`
- **The gate is the holdout, not the whole sample.** The images split deterministically in
  two — a hash of the card id, so there is no seed to lose and the same card lands in the
  same half on any machine. The tuner is allowed to read failures from the tune half only;
  the holdout is the measurement. `overall_accuracy` is still reported and is still useful,
  but it includes the half the prompt was fitted against, which is exactly the number the
  paragraph below says means nothing about the next card. Current split: 82 tune, 68
  holdout, 150 together. **`PKMNSCAN_T1_SPLIT=tune`** restricts a run to that half, which is
  what prompt iteration should use — it halves the upload and keeps the holdout from being
  consulted on every attempt, itself a slow way of fitting to it. The holdout's card-level
  failures are deliberately not printed for the same reason; **`PKMNSCAN_T1_REVEAL_HOLDOUT`**
  opts into seeing them, and the moment a tuner reads them the holdout has become tuning data
  and the score stops measuring generalisation.
- **A cache miss refuses; IT NEVER SUBMITS.** T1 replays banked responses, so an ordinary
  `make harness` makes no API call — and when there is nothing to replay it fails with
  instructions rather than spending. That rule is cause-independent by design, and it was
  not always: the moved-prompt case was guarded and every other cause of a cold cache fell
  straight through to a fresh submission of ~150 images, **under the Stop hook, at the end
  of every turn**. Found on 2026-08-29 in a git worktree, where `harness/.cache/` is
  gitignored and therefore does not travel; nothing was billed only because that worktree
  had no key either, which is luck rather than a design. Submitting is now an act —
  `PKMNSCAN_RERUN_T1=1` — and `make worktree-setup` is how a worktree answers the refusal
  without paying for an answer this machine already holds.
- **AN ORDINARY RUN REPLAYS NOTHING, AS OF 2026-09-06 (D112).** Between two turns the only
  things about T1 that can change are its prompt, its eval set and its arithmetic; the model is
  pinned and the answers are banked. All three now carry fingerprints, so when they agree with
  what `harness/results/t1.json` was generated under, the test ASSERTS the committed
  measurement against its own floor instead of re-deriving a number it cannot change. **It is
  not a skip**: three hashes are compared and the floor is checked, and any mismatch falls
  through to the real replay. Measured: **3 ms**, against a replay that needed every one of the
  150 images on disk.
- **The labels are tracked and the images are not, and that is the split that matters.**
  `harness/eval/manifest.json` (40K) is the ground truth — every field of an `EvalCard` but
  `image`, which is a FILENAME. The 133M mirror beside it is needed only to SUBMIT. Until this
  was separated, the labels were filed with the pixels, which is why T1 failed in a fresh
  checkout, in a worktree before `make worktree-setup`, and could not run in CI at all — not
  because scoring needed the images, but because the labels were stored among them.
- Rerun after any prompt change. Commit the score to `harness/results/` so regressions are
  visible in the diff. One file per configuration — a hinted run and an unhinted run are
  different measurements and must never share a filename. **No date in the name**: git
  holds the history, and a dated filename turned every new UTC date into a fresh file
  rather than a comparison, which is exactly the noise the next bullet forbids.
- **The results file is rewritten only when the measurement changes.** A cached re-scoring
  recomputes nothing, so it leaves the file byte-identical rather than restamping
  `generated_at`. Otherwise every `make harness` puts a one-line diff on a tracked file and
  a real re-measurement stops being visible among the noise — which is the one thing the
  committed score exists to show. `batch_ids` and `usage` are part of the comparison, so a
  fresh submission always writes even if the accuracy lands on the same number.
- **The rarity-clause A/B was run on 2026-08-23 and the clause lost.** `PKMNSCAN_T1_RARITY=1`
  scores the eval with each card's TRUE rarity as a one-element stack claim — the best case
  the feature could ever see — into its own results file, `harness/results/t1-rarity.json`
  (one file per configuration, as above). Measured against baseline: holdout 0.9706 → 0.9559,
  high-confidence misses 5 → 7, and the finish distribution hardened (`unknown` 27 → 5,
  `normal` 66 → 111) despite the clause's own carve-out sentence — the exact both-directions
  failure the Someday entry warned about, plus a third nobody predicted. The losses were name
  misspellings, not rarity-adjacent; the join key improved by one; and the confident-digit
  miss (`271/167`) survived, which is the class D23 says only the catalog cross-check catches.
  **The production clause is therefore switched off** in `cli/cmd_identify.py` with the
  measurement cited at the switch; the claim's other two jobs — the ladder cross-check and
  the chip narrowing — are unaffected. Cost of knowing: $0.17.
- **Known blind spot**: official API images show no foil texture, so T1 cannot validate the
  `finish` field. Do not let a green T1 be read as variant detection working. **Gate B did
  that job on 2026-08-22 and the answer was bad**: 16 of 53 normals read as foil, a 30%
  false-positive rate, and detection agreed with itself across every duplicate pair — both
  Thievuls, both Eiscues, both Pyroars — so it is systematic sheen under the rig's lighting
  rather than noise. D3's disagreement routing carried all 16 to a human instead of to a
  wrong listing, which is the ladder working. The blind spot is therefore no longer that
  the number is unknown; it is that T1 still cannot see it, so this test will stay green
  while that rate is anything at all.

**Below the floor, tune the prompt — but never against the cards you score on.** Fixing the
specific images that failed and re-measuring on the same set reports a number that means
nothing about the next card, and that number is the whole basis for trusting identification
once there is no answer key. So: hold out a slice the tuner never sees the failures from,
tune against the rest, and report only the held-out score. `PKMNSCAN_REFRESH_IMAGES=1` with
a different `EVAL_SETS` draws a fresh sample.
