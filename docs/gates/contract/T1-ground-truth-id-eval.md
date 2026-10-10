### T1 — Ground-truth ID eval

Download ~150 official card images from pokemontcg.io across at least 3 sets as labeled
fixtures (the API record IS the label). Run identification against them. Report accuracy
per set and overall.

- **Pass**: `holdout_accuracy >= 0.95`
- **The gate is the holdout, not the whole sample.** The images split deterministically in
  two. The split is a hash of the card id, so there is no seed to lose. The same card lands in
  the same half on any machine. The tuner is allowed to read failures from the tune half only.
  The holdout is the measurement. `overall_accuracy` is still reported and is still useful,
  but it includes the half the prompt was fitted against. That is exactly the number the
  paragraph below says means nothing about the next card. Current split: 82 tune, 68
  holdout, 150 together. **`BANCHI_T1_SPLIT=tune`** restricts a run to that half, which is
  what prompt iteration should use. It halves the upload and keeps the holdout from being
  consulted on every attempt. That is itself a slow way of fitting to it. The holdout's
  card-level failures are deliberately not printed for the same reason. **`BANCHI_T1_REVEAL_HOLDOUT`**
  opts into seeing them. The moment a tuner reads them, the holdout has become tuning data
  and the score stops measuring generalisation.
- **A cache miss refuses; IT NEVER SUBMITS.** T1 replays banked responses, so an ordinary
  `make harness` makes no API call. When there is nothing to replay, it fails with
  instructions rather than spending. That rule is cause-independent by design. It was not
  always. The moved-prompt case was guarded. Every other cause of a cold cache fell straight
  through to a fresh submission of ~150 images. The submission ran **under the Stop hook, at the
  end of every turn**. Found on 2026-08-29 in a git worktree, where `harness/.cache/` is gitignored and
  therefore does not travel. Nothing was billed only because that worktree had no key either.
  That is luck rather than a design. Submitting is now an act — `BANCHI_RERUN_T1=1` — and
  `make worktree-setup` is how a worktree answers the refusal without paying for an answer
  this machine already holds.
- **AN ORDINARY RUN REPLAYS NOTHING, AS OF 2026-09-06 (D112).** Between two turns the only
  things about T1 that can change are its prompt, its eval set and its arithmetic. The model
  is pinned and the answers are banked. All three now carry fingerprints. So when they agree
  with what `harness/results/t1.json` was generated under, the test ASSERTS the committed
  measurement against its own floor. It does so instead of re-deriving a number it cannot
  change. **It is not a skip**: three hashes are compared and the floor is checked. Any
  mismatch falls through to the real replay. Measured: **3 ms**, against a replay that needed
  every one of the 150 images on disk.
- **The labels are tracked and the images are not, and that is the split that matters.**
  `harness/eval/manifest.json` (40K) is the ground truth. It holds every field of an
  `EvalCard` but `image`, which is a FILENAME. The 133M mirror beside it is needed only to
  SUBMIT. Until this was separated, the labels were filed with the pixels. That is why T1
  failed in a fresh checkout, in a worktree before `make worktree-setup`, and could not run in
  CI at all. It was not because scoring needed the images. It was because the labels were
  stored among them.
- Rerun after any prompt or model change, unless the owner waives a model swap. A waiver is recorded as `model_waiver` in the result file, and the score stays the measured model's. Commit the score to `harness/results/` so regressions are
  visible in the diff. One file per configuration — a hinted run and an unhinted run are
  different measurements and must never share a filename. **No date in the name**: git holds
  the history. A dated filename turned every new UTC date into a fresh file rather than a
  comparison. That is exactly the noise the next bullet forbids.
- **The results file is rewritten only when the measurement changes.** A cached re-scoring
  recomputes nothing. So it leaves the file byte-identical rather than restamping
  `generated_at`. Otherwise every `make harness` puts a one-line diff on a tracked file. A real
  re-measurement stops being visible among the noise. That is the one thing the committed score
  exists to show. `batch_ids` and `usage` are part of the comparison. So a fresh submission
  always writes, even if the accuracy lands on the same number.
- **The rarity-clause A/B was run on 2026-08-23 and the clause lost.** `BANCHI_T1_RARITY=1`
  scores the eval with each card's TRUE rarity as a one-element stack claim. That is the best
  case the feature could ever see. It writes into its own results file, `harness/results/t1-rarity.json`
  (one file per configuration, as above). Measured against baseline: holdout 0.9706 → 0.9559,
  high-confidence misses 5 → 7, and the finish distribution hardened (`unknown` 27 → 5,
  `normal` 66 → 111). That happened despite the clause's own carve-out sentence. It is the
  exact both-directions failure the Someday entry warned about, plus a third nobody predicted.
  The losses were name misspellings, not rarity-adjacent. The join key improved by one. The
  confident-digit miss (`271/167`) survived, which is the class D23 says only the catalog
  cross-check catches. **The production clause is therefore switched off** in
  `cli/cmd_identify.py` with the measurement cited at the switch. The claim's other two jobs —
  the ladder cross-check and the chip narrowing — are unaffected. Cost of knowing: $0.17.
- **Known blind spot**: official API images show no foil texture, so T1 cannot validate the
  `finish` field. Do not let a green T1 be read as variant detection working. **Gate B did
  that job on 2026-08-22 and the answer was bad**: 16 of 53 normals read as foil, a 30%
  false-positive rate. Detection agreed with itself across every duplicate pair: both
  Thievuls, both Eiscues, both Pyroars. So it is systematic sheen under the rig's lighting
  rather than noise. D3's disagreement routing carried all 16 to a human instead of to a
  wrong listing, which is the ladder working. The blind spot is therefore no longer that
  the number is unknown. It is that T1 still cannot see it. So this test will stay green
  while that rate is anything at all.

**Below the floor, tune the prompt — but never against the cards you score on.** Fixing the
specific images that failed and re-measuring on the same set reports a number that means
nothing about the next card. That number is the whole basis for trusting identification
once there is no answer key. So: hold out a slice the tuner never sees the failures from,
tune against the rest, and report only the held-out score. `BANCHI_REFRESH_IMAGES=1` with
a different `EVAL_SETS` draws a fresh sample.
