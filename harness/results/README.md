# Harness results

T1's accuracy score is committed here after every run, so a regression shows up in a diff
instead of in someone's memory of last week's number. See docs/GATES.md.

One file per **configuration**: `t1.json`, `t1-set_hint.json`. Each carries at minimum the
overall accuracy, the per-set breakdown, the image count, the model id, and a hash of the
identification prompt — a score without the prompt that produced it cannot be compared to
anything. A hinted run and an unhinted run are different measurements and must never share
a filename. A re-scoring that recomputes nothing rewrites nothing: an unchanged measurement
leaves the file byte-identical rather than restamping it.

**No date in the filename.** The date is `generated_at` inside the file, and the history is
git's — which is what "a regression shows up in a diff" already meant. A dated name defeated
the rule above, because the write compares against the file it is about to write: a new UTC
date meant a new filename, nothing to compare, and an unconditional write. One measurement
became one file per day the harness ran.
