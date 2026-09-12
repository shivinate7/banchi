## D112 — The labels are tracked, the images are not, and an unmoved measurement is asserted rather than re-derived

**Built 2026-09-06, on the owner's observation.** Asked whether T1 still needed to run as often
as it does, they put it plainly: *"t1 as a job doesn't seem like something that needs to run
this often anymore."* That is right, and the reason it was running is worth writing down.

**WHAT T1 COULD LEARN BETWEEN TWO TURNS WAS NOTHING.** The model is pinned, the responses are
banked in `harness/.cache`, the labels are fixed and the floor is a constant. So an ordinary
`make harness` loaded 150 images off disk, replayed a run submitted on 2026-08-03, and
recomputed the same 0.9706 it recomputed the turn before — at the end of every turn, under the
Stop hook. The number was evidence; the recomputation was ceremony.

**Only three things about it can move, and now all three have fingerprints.** The prompt had
one. The eval set had one. **The arithmetic did not**, and that omission was the only honest
reason to keep replaying: an edited scorer could have left the committed number stale with
nothing to notice. `scorer_fingerprint()` closes it, hashing the per-card comparison, the
per-set aggregation, the holdout split and the floor — the source of those functions and not of
the module, because hashing the file would make a comment edit demand a measurement that costs
money, the same trap `prompt_fingerprint` already documents avoiding.

**So the ordinary path asserts instead of re-deriving, and it is not a skip.** Three hashes are
compared against what `harness/results/t1.json` was generated under, and the committed holdout
is held to its own floor. Four checks, all named in the output. A mismatch on any of them falls
straight through to the replay, which is where the images and the money are.
**Measured: 3 ms**, against a replay that required all 150 images to be present.

**THE SPLIT THAT MADE IT POSSIBLE IS THE LABELS, AND THEY HAD BEEN FILED WITH THE PIXELS.**
`EvalCard`'s own docstring says every field but `image` is ground truth, and `image` is a
FILENAME. That ground truth already existed, serialized, as `manifest.json` — 40K — and it lived
inside `harness/images/`, which is gitignored because the 133M of pictures beside it are. So the
labels were untracked for the pictures' reason rather than for their own. Moved to
`harness/eval/manifest.json` and tracked; the old location is still READ so a machine that has
one is not made to re-download, and never written.

**What that fixes beyond the cadence**: T1 now runs in a fresh clone, in a worktree that has not
had `make worktree-setup`, and in CI — none of which it could do before, and none of which was
ever about needing the images. The mirror is now a requirement of re-measuring only, which was
always a deliberate, paid act.

**What was NOT done, and the measurement is why.** The owner also asked to drop T1 from the Stop
hook. At 3 ms that buys nothing and costs the thing worth having: a prompt edit is caught at the
end of the turn that made it, rather than whenever somebody next runs the fuller gate. The
request was answered by making the work disappear rather than by moving it. Reopen this if T1
ever grows a cost again.

**The committed `generated_at` was restored by hand to 2026-08-23** after the migration replay
rewrote it. Adding a field is not a re-measurement, and the timestamp on a score should name the
run that produced it. The number, the model and every per-set figure are byte-identical.

**A CONSEQUENCE WORTH ITS OWN LINE: the harness became hermetic, so CI now runs it.** All nine
tests pass on a clone with no images and no cache — measured, not inferred — so
`make ci-check` gained the `harness` row the day after it was written to exclude it. The
workflow that guards this repo went from twelve of fourteen checks to thirteen, and the only
one left out is `vale`, which needs a binary the runner does not have and has never gated a
commit. Nothing there can spend money: a re-measurement needs an explicit flag AND a key.

**What retires this:** a T1 whose inputs stop being frozen — a model that floats, or an eval set
that regenerates — at which point re-deriving each run means something again.
