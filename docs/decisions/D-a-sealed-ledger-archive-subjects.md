## D-a-sealed-ledger-archive-subjects — The subject list widens to the order ledger, and sealed product joins it

**MEASURED AGAINST THE OWNER'S REAL STORE, 2026-09-20.** 539 distinct SKUs have sold.
Together they total $66,334.71 gross (canceled excluded, D214's own rule). 270 of them
carry no row in `cards` at all. Those 270 total $61,655.49 — 92.9% of gross.
`pipeline/pricearchive.py:rows_from_store` built its subject dict from `cards` alone. That
is why the archive covered 0.4% of gross before this entry. This closes the gap D223 named and left unsolved.

The owner's own word: *"given you have my sealed's export data too with price sold and
what item/sku, you can literally bring just as informative history information on them
despite not having seen them come through the front door."*

### The stale premise, named rather than repealed

D223 argued the subject list is `cards.sku`, by D219's own settled argument. It argued no
ranking of that list can put a SKU on it that was never there. That premise held for every
SKU a physical card was ever photographed against. It went stale the moment the owner's
ten biggest sellers turned out to be SKUs with no photograph at all. D223 measured this
itself. It proposed two fixes and built neither: give `OrderLine` a `set_name` the feed
already sends, or build a separate resolver for sealed product. This entry takes the
second path. `OrderLine` is untouched — D223's own reason still holds, that adding a
column nothing else reads is a schema change past one task's fence. Instead, the `name`
`OrderLine` already carries is parsed.

### `OrderLine.name` already carries every cell an export-shaped row needs

An order line's `name` is TCGplayer's own canonical display string. Its shape is
`<Product Line> - <Group Name>: <Product Name>[ - #<Number>] - <Condition>`. This was
verified across a random sample of 25 of the 270 ledger-only SKUs.
`pipeline/pricearchive.py:parse_ledger_name` is a pure function over this grammar — no
store, no network. `pipeline/pricearchive.py:ledger_subject_rows` is the caller. It
resolves the group boundary against a real `Market.groups(category_id)` answer. It turns
a whole SKU into an export-shaped row, or a named refusal.

**The group boundary is resolved, never guessed by splitting on the first `": "`.** A
group name itself carries a colon (`SV09: Journey Together`). A first-split reads `SV09`
alone. That resolves to nothing. `pipeline/pricearchive.py:_longest_group_prefix` walks
every `": "` in the remainder. It keeps the LAST, and therefore longest, prefix that names
a real group in `Market.groups`'s own answer. `scripts/pricearchive-selftest.py` proves
the naive first-split fails on exactly this case. It then proves the longest-prefix match
succeeds on the same case.

**A blank Number is a correct sealed answer, never a refusal.** Sealed lines carry no
`#<Number>` segment at all. `pipeline/pricehistory.py:ProductIndex`'s own docstring
already argues a blank Number is an expected shape one hop downstream. This entry does not
invent that case.

**Every unparseable name is a named refusal, never a drop.** This is `CLAUDE.md`'s
both-directions rule. An unshaped name, an uncatalogued product line, and a group the
mirror's own list does not carry all report the SKU and why. `rows_from_store`'s new
`refusals` out-parameter carries them. `cli/cmd_pricearchive.py` prints them before the
pass begins.

### `cards` still wins, by construction

`ledger_subject_rows` is only ever asked about a SKU that `rows_from_store`'s own `cards`
walk did not already answer for. There is no later merge step to get backwards. No test
was needed to prove a conflict rule the call order already makes structurally true.
`scripts/pricearchive-selftest.py` still proves it directly. A SKU present as both a card
and a ledger line, under two different names, resolves to the card's own name.

### This amends D224's "no network call" premise, narrowly

D224 argued the preview reads `rows_from_store` — "pure, no network" — and the archive's
own table, and nothing else. That was true when the subject list was `cards` alone. It is
no longer exactly true. Resolving a sealed SKU's own Set Name needs
`Market.category_id`/`.groups`. Both are cached, whole-CATEGORY reads: one request per
distinct Product Line this ledger has ever sold, never per SKU, per D219's own TTL. A
store with no sealed sales, or a mirror already warm on disk, still previews for nothing.
The one exception is the first preview after a genuinely new sealed sale. That exception
is bounded by the number of Product Lines this repo catalogues — three, today.
`cli/cmd_pricearchive.py`'s own docstring says so now. D224's larger claims are untouched:
no re-fetch of the archived buckets themselves, commit-per-chunk, resumable.

### What this does not touch

`rank_by_revenue`'s own ranking logic is unchanged. It was already handed every key
`revenue_by_sku` can answer for (D223's own note). Widening the
subject set only stops most of those keys from being discarded before they reach it.
`chunk_rows` is unchanged. `pipeline/` still imports nothing new from `store/` beyond what
`pricearchive.py` already imported. `fixtures/` is untouched.

### The measured reach of this fix

This was measured read-only against the owner's real store, 2026-09-20. Nothing was
written. No `pkmnscan archive` command was run — a live sweep was in progress against the
same store, and only `ledger_subject_rows` was called, never `sweep`. 287 SKUs in the
ledger carry no `cards` row today (D223's own count of 270 was taken a day earlier, over a
store that has since sold more). 281 of the 287 resolve to a row. The remaining 6 all
share one reason: an uncatalogued product line this repo does not track at all — `YuGiOh`,
`Card Sleeves`, `Playmats`. Every one of those is a real refusal, not a bug — this repo has
no Yu-Gi-Oh! or supply taxonomy to resolve against, and D22's own registry does not claim
one.
