# Harness results

T1's accuracy score is committed here after every run, so a regression shows up in a diff
instead of in someone's memory of last week's number. See docs/GATES.md.

One file per run: `t1-<UTC date>.json`, carrying at minimum the overall accuracy, the
per-set breakdown, the image count, the model id, and a hash of the identification prompt
— a score without the prompt that produced it cannot be compared to anything.

Empty until build-order step 4.
