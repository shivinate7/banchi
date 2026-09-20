## D-archive-live-catalogue-lookup-at-join-time — Recorded, not built: ask the catalogue earlier than the archive does

**What this records.** D237 measured a gap. 8 of 15
identification errors behind the archive's own 16 refusals cannot be caught from stored
data by any rule. This store carries no independent source of truth for a set's real card
list. D15 vendors the Pokemon catalogue locally. Riftbound and the newest Pokemon sets have
no local mirror at all. The only earlier catch is asking the live catalogue. Today that
happens months later, at sweep time.

**The owner's ruling.** Record the option, likely at join time, and do not build it now.
Nothing in this entry is built. `pipeline/join.py`, `pipeline/pricehistory.py` and
`cli/cmd_join.py` are untouched.

**AMENDED 2026-09-20, ON THE OWNER'S CORRECTION.** The cost paragraph below originally
argued this would run "against a host already measured to throttle this client (D222)".
That premise was wrong. D222's throttle is the PRICE-HISTORY host,
`infinite-api.tcgplayer.com`. It refused this client outright after roughly 800 requests
in one sitting. The CATALOGUE lives on a different host, `tcgcsv.com`. It has throttled
nothing across many probes. It answers one request per (category, group), not per card.
The owner ruled that a catalogue set's membership does not change from pull to pull. As of
DEBT34, that answer is now cached forever, rather than re-fetched weekly. The owner's
words: the catalogue is literally free to pull. What follows keeps the original
argument's shape and corrects the one premise that was wrong.

**Why join time, over capture time.** A join is already a networked step. It already asks
the catalogue a question per card, through `Market.product_id_for_row`. A second catalogue
question there costs no new architecture. Corrected above, it costs close to nothing in
practice: one cached, unthrottled request per (category, group), not per card. Capture is
deliberately free and offline (D1's own two-phase split: capture is fast, dumb and never
touches a network). Adding any network call at capture time would put a wait between an
operator and the next photograph, however cheap that call is. That remains the real
argument for join time over capture time. It is not the cost of the call itself, which
this entry now measures as small.

**The cost, corrected.** A join over a box of newly captured cards would ask the catalogue
about each ambiguous card's group. Most cards in one run share a handful of (category,
group) pairs. The group-level cache means the FIRST ambiguous card in a set pays a cached
request. Every other card in that set, that run, pays nothing. This runs against
`tcgcsv.com`, measured to throttle nothing across many probes, and now cached forever.
This is a materially smaller cost than this entry first argued. It does not, on its own,
settle whether to build this. The three open questions below are unaffected by the
correction.

**What is not decided.** Three questions stay open. Which cards would trigger the lookup:
every unresolved card, or only one a check from `D-archive-store-checks` or
the sku-number-contradictions build (a separate PR) already flagged. Whether a failed lookup should block the
join, or fall through to today's behaviour. How the result would be cached, so a re-join of
the same box does not re-ask the same question. None of these is answered here. Building
this is future work, gated on the owner's word.

Cites D1 (why capture stays offline), D15 (the vendored catalogue's own limits), D222 (the
price-history host's own throttle, not the catalogue's), DEBT34 (the catalogue's own
never-expiring cache and why), and D237 (the 8-of-15 measurement this entry answers).
