## D-a-archive-resume-window — The sweep's own resume window is six days, not one hour

**MEASURED AGAINST THE OWNER'S REAL STORE.** Two `archive sweep` passes ran five hours
apart. The second skipped nothing. It started again from the top of the ranked list.

`cli/cmd_pricearchive.py` read `pipeline/pricehistory.py:HISTORY_TTL_SECONDS` (one hour)
and handed it to `pipeline/pricearchive.py:split_by_freshness` as the resume window. A
SKU's own buckets counted as fresh, and so skipped, only inside that hour.

### Why this only worked before, by accident

The first pass ran before `rank_by_revenue` existed (D223). It read
an arbitrary set of names, in whatever order `cards.select` returned. A second pass, an
hour or a week later, landed on a different arbitrary set. It always made SOME progress,
by luck rather than by design.

`rank_by_revenue` made the subject order stable and deterministic. D222 measured the host
throttling this client after roughly 800 requests, twice: 796 and 876. Every future pass
now reads the SAME top ~200 names first, every time, in the same order. Past the one-hour
window, none of them look fresh. The whole budget then goes to re-reading buckets the
archive already holds. The pass never advances past its own top of the list. The archive
would sit at whatever it swept once, permanently. D224's own claim, that a resumed pass is
cheap, is false across any gap longer than an hour.

### The fix: a resume window that outlives a normal gap between presses

`pipeline/pricearchive.py:RESUME_TTL_SECONDS` is six days, the owner's own ruling. A
weekly press refreshes the whole archive. Any pass run again inside the same week
advances onto ground the last pass had not yet covered.

`HISTORY_TTL_SECONDS` is untouched. One hour is the right answer for a different reader
with a different need. The live `#/pricing` screen is that reader. A stale figure there
would mislead. A fresh fetch there is cheap, because it reads one SKU, not nine hundred.
This entry does not argue that reader's own case. It only refuses to keep sharing its
constant with a walk that has nothing in common with it but a name.

`split_by_freshness` itself needed no change. It already took `ttl_seconds` as an
argument — the primitive this fix reaches for, not one it builds around.

### Proof, mutation-tested

`scripts/pricearchive-selftest.py` builds one bucket read five hours before "now." Read
back at the OLD one-hour window, that SKU is stale and is sent back to be re-read — the
defect, proven to fail first. Read back at the NEW six-day window, the same SKU is fresh
and is skipped. A third case, seven days old, is stale even under the new window. The fix
is not "never expire."

`cli/cmd_pricearchive.py:_format_window` prints the window in the unit a person reads it
in — days for six days, hours for one hour. It never prints a shared `// 60` count, which
would read "8640 minute(s)."

### What this does not touch

The subject list, the ranking, `chunk_rows`, and the throttle backoff are all unchanged.
So is the sealed-product widening (`D-a-sealed-ledger-archive-subjects`). This entry is
one number and the string that prints it.
