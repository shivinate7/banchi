## D224 — The preview costs nothing, and the press commits as it goes

**MEASURED AGAINST THE OWNER'S REAL STORE, 2026-09-19.** `archive sweep`
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
`store-scaling` item 2 already named and `cli/resolve.py:_copies_out` already paid for.
`split_by_freshness` then asks, per SKU: does every range this pass wants already have a
bucket read within `pipeline/pricehistory.py:HISTORY_TTL_SECONDS` (one hour) of now?

That hour is not new. `pipeline/pricehistory.py` already argues for it: short enough that
nobody reads a stale figure. Long enough that repeating a pass in one sitting costs no
requests. Reusing it means a sweep resumed within the hour of an interrupt pays for nothing
it already has. Per D222, that resumed-within-the-hour case is now the
NORMAL one, not the exception.

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
method, called more often on smaller inputs. No timer, cron or launch agent is added. The
sweep is still a press a person runs, one invocation or several. D62's statement that this
reader cannot fire by itself is untouched.
