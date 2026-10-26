## D224 — Sweep preview is free; press commits

**MEASURED AGAINST THE OWNER'S REAL STORE.** `archive sweep`
(D219) over 914 SKUs and 4 ranges printed nothing for over ten
minutes. Then it printed the whole report at once. Silence and a hang look identical from
outside.

`archive sweep` with no `--write` made all 3,656 requests anyway. The preview only skipped
the final write, not the walk that earned it.

`archive show` read 0 buckets while a sweep was an hour into running. The store was never
written to until the whole walk finished. One Ctrl-C or one dropped connection lost every
read that hour.

This entry fixes both: what a preview of this press honestly is, and how `--write` survives
an interrupt.

### The preview names what the archive already holds, and touches no socket

Every other free press in this repo previews for nothing. `reprice list`, `prices adopt`
and `reconcile --live` all do. `archive sweep`'s own module docstring already argued there
is no operator judgement inside this walk to protect, unlike `prices adopt`'s real decision
(D86). That argument is right about why a preview costs nothing to skip. It was never
applied to what the preview actually did, which was the walk in full.

The preview now reads two things and nothing else. One is the subject list
(`rows_from_store`, pure, no network). The other is the archive's own table
(`Store().read().archive`, also no network). From those two it says how many SKUs are
subject to the pass. It says how many already carry a bucket of any age. It says how many
are fresh enough (`split_by_freshness`, below) that `--write` would skip them. That is
everything a preview of this press can say honestly. A live figure it did not fetch is not
something to preview. It is something to make up.

### `--write` commits every chunk, never the whole pass, in one transaction each

D88 says one transaction per write. It does not say one transaction per PRESS. A sweep that
walks 914 SKUs and writes once at the end is one enormous transaction wearing D88's name.
It fails D88's own purpose the moment the process dies before reaching the write. Every
bucket read that hour is gone. The archive exists because a bucket lost to the source's
357-day window may be unrecoverable at any later date (D219).

`cli/cmd_pricearchive.py:_sweep` now splits the subject list into chunks of
`pipeline.pricearchive.CHUNK_SKUS` (20). It opens one `Store().write()` per chunk. It
commits that chunk's buckets and the pass's running accounting before moving on. An
interrupt between two chunks loses at most one chunk's reads. That is a few tens of SKUs,
never an hour of them.

### A resumed pass does not re-read what it already holds from this same pass

Committing per chunk only helps if the next run does not throw the work away by
re-fetching it. `freshness_index` builds `sku -> {range: latest 'at'}` in one pass over the
whole archive table. It never walks the table once per subject — the mistake
the per-box inventory read (D192) already named and `cli/resolve.py:_copies_out` already paid for.
`split_by_freshness` then asks, per SKU: does every range this pass wants already have a
bucket read within `pipeline.pricearchive.RESUME_TTL_SECONDS` (six days) of now?

The window is not `pipeline.pricehistory.HISTORY_TTL_SECONDS` (one hour). That hour suits the live
`#/pricing` read. It is too short for this walk. `rank_by_revenue` (D231) reads the same top names
first on every pass. A one-hour window sends each later pass back to them, and it never advances.
Six days lets a weekly press refresh the whole archive. A pass run again within the week moves on
to ground the last one did not cover. Per D222, a resumed pass is the NORMAL case, not the
exception.

A SKU with genuinely no sales in a period never looks fresh by this test. An empty series
writes no bucket row, so there is no `at` to check. That is the safe direction to be wrong
in. Such a SKU is re-read every pass rather than silently skipped. It costs a request. It
never costs data.

### What was proved, and how it was proved to fail first

`scripts/pricearchive-selftest.py` adds a `RecordingMarket`. It remembers every SKU it was
asked about. It can be told to raise on a named one, standing in for a dropped connection.

The suite proves the OLD shape fails first. One `sweep()` call over every row, with nothing
committed until it returns, loses everything when the call raises partway. The store holds
zero buckets afterward.

It then proves the fix. Chunked, one commit per chunk, the chunk before the drop survives.
The chunk after it is never even asked for.

A third pass proves resume. Re-reading the store's own freshness index, the already-
archived SKU is skipped. It never reaches the market again. The still-owed SKUs are read
and archived exactly once.

### What this does not touch

The schema and the key stay `(sku, range, start)` (D219). The
never-delete rule is unchanged. A chunk commits with `PriceArchive.upsert()`, the same
method, called more often on smaller inputs. The sweep is still a press a person can run, one
invocation or several. The daily job also runs it, after the refresh, because the owner ruled
that it runs nightly, on the Mac ("if the day is a new day when my mac is on, just get it done
then"). That adds no launchd agent of its own: the installed daily job passes `--sweep`, and
`scripts/price-refresh-daily.py` calls `cli.cmd_pricearchive` in the same process, at the pace D222
saved. It sweeps once per US Central day, in the first run of that day, and skips when today's
sweep finished. It has no wall-clock cap and no keep-awake, and its pace reads a monotonic clock, so
a sleep does not inflate it. `make price-refresh` is a manual read and sweeps only with `ARGS=--sweep`.
A failed refresh skips the sweep, and the log says so. A second throttle, a host that refused from
the first sku, or a pass that asked and wrote no bucket stops it as a failed `archive` step and
keeps the buckets it wrote. The job still ends 0, and the next run resumes (D222, D224). A night
with nothing left to read, or no sku, is ok. The sweep's result is one more step in the `#/pricing`
note.
