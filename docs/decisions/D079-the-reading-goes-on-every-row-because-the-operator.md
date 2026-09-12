## D79 — The reading goes on every row, because the operator answered D62's own measurement

**Built 2026-08-31, on the owner's ask: "Can we use this blank space in pricing between card and market to load and show the daily + weekly graphs that T loads?"**
This is not a reopening. D62 closed with the condition for its own amendment and named the
remedy in the shape it has been built: *"What would reopen this: the panel being opened on
every card… the honest answer is a batched route — `readings_for_rows` already exists in the
module and groups by productId — and a column on the row rather than a panel beside it. The
measurement is whether the operator presses `T` more often than they press `H`."* The
operator is the person who asked, and asking for the graphs on every row is that measurement
answered out loud.

**So what changed is the GRANULARITY OF THE PRESS AND NOT WHETHER THERE IS ONE, which is the half of D62 that survives untouched.**
That entry made the read a press because a follow-focus panel would fire one request per
arrow key at a free public mirror. Batching does not make those requests cheap —
**measured on `2026-08-31-box3-01`: 46 SKUs, ~92 requests, 37.7s cold and 0.15s warm**— it
makes them ONE DECISION instead of fifty. Nothing polls the route and no render fires it; a
`useEffect` on mount would spend that walk on every visit to `#/pricing` for readings nobody
asked for, which is D62's rudeness arriving by the other door.

### The blank space is not blank, and that is the request's one wrong premise

`--pricing-cols` gives the card `minmax(0, 1fr)` and every other column a fixed width. The card
is therefore not a wide column with room in it — it is
**whatever is left after the fixed ones**, so the gap the graphs were asked to fill is a
function of the window: generous at 1512px,
**zero at about 1150px, where the names are already truncating.** Drawn into that slack the
strip would be wide on a monitor, absent on a laptop, and would have taken the card name's
last readable characters on the way there.

**It is a real 168px column and it comes off the name deliberately, at every width.** Two
80px sparks with `--s2` between them. The cost is stated rather than hidden: at 1512px the
name keeps ~356px of the ~536px it had; at 1100px it drops to ~124px and truncates to
`Rengar, Trophy H…`. That is the trade, and it is the owner's to reverse by narrowing the
column or dropping the weekly spark.

**AND IT MOVED A HARD-CODED COLUMN INDEX THAT NOTHING WOULD HAVE CAUGHT.**
`.pricing-row-note` was `grid-column: 2 / -1` — the card, then everything after it.
Inserting a column at 2 put the note in the trend column's second row, which left
`.pricetrend` (spanning both rows, as
`.pricing-id` does) with nowhere to sit, so it was pushed into an implicit twelfth column off
the right edge and
**every figure slid one column left, on the rows carrying a note and not on the rows without.**
The caption stayed put, so it read as the reference block having come unaligned from its own
headings. The types check, `make lint` is clean, and `make design-check` has no floor over it. Found by
looking at the screen.

### A shape and a sign. No money on the row, ever

The row already carries four dollar columns and the field a listing price is typed into. A
fifth figure here would be a **reading** rather than a price, sitting inches from that
field, and the distance between reading it and copying it across is one keystroke. D8 makes
the export the pricing source and D62 refused to reopen it by name; `$16.33 avg sale` on
this row is that refusal being spent quietly rather than argued.

So the `vwap`, its bound, the liquidity and the within-bucket spread all stay on `T`'s panel,
where there is room to draw the anchor at size and the bound muted beneath it.
**The two drawings answer two different questions**— the panel says what one card is worth,
the strip says which of forty-six is moving — and that is why they are two routes with two
payloads rather than one route with a mode. `_history_spark` carries a range name, its span,
the momentum FRACTION and the bucket market prices; `_history_series` carries everything,
and sending it forty-six times would be ~19,000 numbers to draw one field of five.

### The caveats are stated once, above the list, and not forty-six times

D62's panel owes a reader three things and an 80px cell can carry none of them: that the
ranges OVERLAP and routinely point opposite ways, what span each covers, and that the wider
one can be the staler. They go in one line under the presets.
**That is honest because the spans are identical across every SKU of a run**— measured, all
46 on the run this was built against, both ranges — which is a fact about bucket boundaries
being global rather than per product, and the reason a per-row date would have been
forty-six copies of one string.

Direction stays a sign and never a color, which is D62's rule and binds harder on a list: a
colored percentage would be the loudest thing on the screen, over the least authoritative
thing on it.

### The rows this run can add nothing for are skipped, and stay reachable

The owner's second instruction: *"I don't need the prices for the rows that have none
left."*
`at_cap` is the field `cli/cmd_join.py` already writes and the same one those rows are grouped
under,
**so the filter and the grouping agree by construction rather than by two rules kept in step.**
14 of the 60 SKUs on that run, so 28 requests never made.

**They are not unreachable, and that is what makes the default safe.** `T` reads any one of
them, and an explicit `?sku=` overrides the filter — a caller naming a row has already
decided. The skip is a default over the run, never a rule about a SKU.

**And the count is on screen rather than implied.** A strip drawn over 46 of 60 rows with no
number beside it reads as fourteen failures; `46 read · 14 not asked` is what stops that.

### Chunked, sequential, and abandoned on a run change

Eight SKUs a request, walked in order — six waves instead of one 37-second blank, first
answer in about five seconds. **`Promise.all` over the chunks is refused**: it would finish
six times sooner by racing six sockets at a host that publishes no rate limit and asks
nothing of us, which is exactly the courtesy `pipeline/pricehistory.py` spends a constant
on. **The wall clock is not what is being optimised; the blank screen is.**

A generation counter abandons a walk in flight when the run changes or the button is pressed
again — without it a read started over run A keeps filling run B's column, one chunk at a
time, for the rest of the half-minute. And the strip is CLEARED on a run change where
`history` is deliberately kept: a reading is a fact about a CARD, but *which rows are still
open* is a fact about the run.

### Both directions, and a dead chunk is eight refusals rather than a stopped walk

Every asked SKU comes back in `skus` or in `refused` — the promise `readings_for_rows` makes
one layer down, kept across the two filters this route applies on top. The client spends it:
a SKU in neither map is written as a refusal naming that, because a SKU left on `reading…`
for the rest of the session is the silent drop `CLAUDE.md` forbids wearing a spinner. A
mirror having a bad minute costs the rows it was asked about and not the thirty behind them.

**What is not built, named rather than left to be discovered.** No sort by momentum — the
list order is `cli/cmd_join.py`'s and D28 forbids it moving under a finger. No `watch_above`
alarm, which is still the reading that would make one worth having (D49). No third range:
`quarter` and
`semiannual` are reachable and `DEFAULT_RANGES` is two, for the reason it has always been two.
No strip on `#/inventory` — D62's ruling that a reading belongs where a price is decided is
not disturbed by this.

**What would reopen this: the column being read on every visit.** It is a press because the
walk costs 37 seconds and ~92 requests at somebody else's mirror. If it turns out to be
pressed on arrival every single time, the honest answer is a cache with a life longer than
the hour
`HISTORY_TTL_SECONDS` gives it, argued on its own terms — not an effect that fires the walk
without being asked.
