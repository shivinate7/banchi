# Harness results

T1's accuracy score is committed here after every run, so a regression shows up in a diff
instead of in someone's memory of last week's number. See docs/GATES.md.

One file per date **and configuration**: `t1-<UTC date>[-<config>].json`, carrying at
minimum the overall accuracy, the per-set breakdown, the image count, the model id, and a
hash of the identification prompt — a score without the prompt that produced it cannot be
compared to anything. A hinted run and an unhinted run are different measurements and must
never share a filename. A re-scoring that recomputes nothing rewrites nothing: an unchanged
measurement leaves the file byte-identical rather than restamping it.
