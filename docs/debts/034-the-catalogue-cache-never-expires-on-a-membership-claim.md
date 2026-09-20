## 34 — The catalogue cache never expires, on a membership claim this store cannot re-check on its own

**No work proposed.** `pipeline/pricehistory.py:CATALOG_TTL_SECONDS` is `float("inf")` as of
this entry. The owner ruled: the set of cards in a catalogue set does not change from pull
to pull. Confirmed independently across settled Pokemon sets. Recently-modified products
all carry their original low product ids. No new ids appear. What churn exists is a field
edit to an existing record, never an addition.

**The trade, named rather than hidden.** A cache that never expires trades
correctness-by-expiry for disk, and for staleness nothing will ever repair on its own.
Today that trade is a clear win. The owner holds roughly 900 subject SKUs across a handful
of sets. The cache is small. A wrong entry is fixable by deleting a derived directory.

**What would force a different answer, named rather than left vague.** Either of two
things. Cache size on disk becoming material. Or the store covering enough sets that ONE
corrupted or partial entry stops being cheap to notice by hand. Neither is true yet.

**Genuinely unmeasured, and cheap to check later.** Whether the mirror ever CORRECTS a
collector number on an existing card. That is the one field `pipeline/join.py` actually
reads off the catalogue. Two snapshots of the same group, a week apart, would settle this
at no request cost — a diff of `by_number` keys between them. Not chased now.

**Why `Market.prices` was not swept into this.** It answers a group's CURRENT prices,
which move daily, not a set's membership. `PRICE_TTL_SECONDS` is its own constant, unchanged
in value from the shared constant this replaces. Sharing the new infinite lifetime would
have silently made a daily price permanent, the opposite of the owner's ask.

**Why this saves more than disk.** The catalogue lives on `tcgcsv.com`, measured to
throttle nothing across many probes. The price-history host, `infinite-api.tcgplayer.com`,
refused this client outright after roughly 800 requests in one sitting (D216's own
finding). Every future sweep now spends its request budget establishing prices, not
re-confirming a membership fact that cannot change.

Cites D216 (the price-history host's own throttle), D219 (the archive that spends this
budget), and D234 (the join that reads a catalogue number).
