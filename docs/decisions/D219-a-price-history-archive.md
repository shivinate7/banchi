## D219 — The archive key carries the range, and the archive never deletes

**THE SOURCE WINDOW SLIDES.** Everything not captured ages out for good.
`pipeline/pricehistory.py`'s history endpoint answers `annual` at 357 days wide. No range
goes wider. `week`, `year`, `all` and `latest` all answer HTTP 400. A bucket that falls out
of that window cannot be asked for again. Not from any range. Not at any later date.
`store/pricearchive.py`'s `price_history` table is the local, permanent copy this repo did
not have before this entry. `pipeline/pricearchive.py` walks the endpoint for every SKU this
store has sold or holds. `pkmnscan archive sweep --write` is the press that runs it. Both are
new. `pipeline/pricehistory.py`'s own fetching and parsing are untouched.

### Why the key carries `range` and not `width_days`

D62 already settled the underlying fact. The four ranges overlap on the calendar.
Concatenating them double-counts. One calendar day is a one-day bucket in `month`. The same
day sits inside a wider bucket in a broader range. Those are two different facts. D62
forbids merging them.

The naive fix looks safe at first. Key a stored bucket on `(sku, width_days, start)` instead
of on the range name. That looks like it satisfies D62, until you read
`pipeline/pricehistory.py`'s own table of ranges (line 41):

```
range=       buckets x width      span
month        30 x 1 day           29 days
quarter      30 x 3 days          87 days
semiannual   26 x 7 days          175 days
annual       52 x 7 days          357 days
```

`semiannual` and `annual` are **both seven-day buckets**. A width-keyed table would fold a
semiannual bucket and an annual bucket into one row. That happens whenever the two start on
the same date. It is the exact D62 collision this table exists to prevent. It would happen on
the most recent 175 days. Every sweep touches that span every time.

So the key is `(sku, range, start)`. `product_id` and `width_days` are stored as plain
columns. A reader can join or sort on them. Neither is part of the key. A SKU never belongs
to two products, so `sku` alone already carries what `product_id` would add. `width_days` is
a fact *about* a row (`RANGE_WIDTH_DAYS[range]`). It is not a second way to tell two rows
apart.

### Why the archive never deletes a row

`store/readings.py`'s `Readings.replace()` (D189) is a full clear-then-reinsert. It runs on
every `readings adopt --write`. That is correct there, because `readings` is a cache of files
**still on this machine's disk**. A run directory or a live export that has been deleted
really should drop out of the table. The file it described no longer exists to be asked about
again.

`price_history` has no such second copy. Once a bucket falls out of the source's 357-day
window, this table is the only place its numbers exist. A press that cleared the table on
every sweep would delete exactly the observations this feature exists to keep. So would a
press that only kept whatever the current subject SKUs still resolve to. Either one loses
data. That loss can happen the moment a card is sold, a SKU stops being catalogued, or an
operator's own query narrows.

So `PriceArchive.upsert()` only ever adds a key it has not seen. It may also overwrite a key
it has, but only with a fresher reading of the *same* bucket. The endpoint has been observed
to correct a week's own totals shortly after it closes. A re-read keeps a still-open bucket
accurate. A bucket no later sweep mentions is left exactly as it was, forever. That covers
both cases: it aged out of the source, or that SKU was outside this pass's subject list.

### The subject is the `cards` table's own distinct SKUs

"The names the owner has sold or holds" is read directly off `cards.sku`. A card keeps its
SKU for as long as its record exists, sold or not. D26 retires a card to a state. D134 buries
a departed box's photographs and record into the graveyard. Neither deletes the row from
`cards`. `pipeline/pricearchive.py:rows_from_store` selects `(sku, name, number, set_name,
condition, game)` for every card, keyed by SKU. It builds one export-shaped row per SKU. That
is exactly the shape `pipeline/pricehistory.py:Market.readings_for_rows` already consumes for
a real export row. This module invents no second resolution path against the catalog.

### What was proved, and how

`scripts/pricearchive-selftest.py` runs against a throwaway store. `PKMNSCAN_HOME` points at
a temp directory, destroyed after. A stand-in for `Market` carries no network underneath, per
`CLAUDE.md`'s "no network call in a test" rule. It asserts the one test this entry exists for.
The test proves the defect this entry guards against: archiving the same calendar day from
`semiannual` and `annual` — both seven-day buckets — leaves **two** rows. Each carries its
own range and its own market figure. The same script shows a width-only key merging them
into one.

### What this does not touch

No route. No client function. No screen. `pipeline/pricehistory.py`'s fetching and parsing
are unchanged. No timer, cron or launch agent runs this sweep on its own. The owner asked for
a schedule and the schedule is deferred, by the owner's own word
(`docs/specs/revenue-plan.md` §4, `docs/specs/revenue-next.md` "The archive comes first"). A
sweep firing on its own reverses D62's own statement. D62 says this reader cannot fire by
itself. That reversal needs its own argument, which nobody has made yet.
