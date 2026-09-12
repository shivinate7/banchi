## D115 — The reading is what the export said, and what has sold since is counted beside it

**Built 2026-09-07, after the operator asked why the ordering was confusing.** Their
`reconcile --live` reported **92 copies across 56 SKUs as `unexplained`** — pushed by this
pipeline, not held by TCGplayer, no card marked sold — and the cause was cards they had pulled
and never marked. The obvious repair is to reconcile and then mark those sold. Doing it in that
order counted every one of them twice.

Their question was the entry: *"any advice on if there's better logic we can keep here so it's
not so confusing? this feels a little unintuitive despite making sense."*

### Three writers, three meanings, and a timestamp race between them

`store/master.py:Listing.live` was written by three things that meant different things:

| writer | meaning | dated `live_as_of` |
|---|---|---|
| `observe_live()` | the export's **reading** | the export file's mtime |
| `bump(LIVE, ±1)` | a sale's **delta** | **`now()`** |
| `release(budget)` | D34's box-delete **assertion** | `now()`, if it reached `live` |

**A reading and a delta are not the same kind of fact, and "newer wins" cannot arbitrate them.** Worse, `bump` on `LIVE` also restamped `live_as_of = now()` — **a sale claimed to be a fresh reading of TCGplayer that nobody had taken.** That forgery is what let one copy be
subtracted twice: `reconcile --live` wrote TCGplayer's figure, which already reflected the
sale, and marking the card sold then decremented it again.

`bump` floored at zero, so on a row already at `live: 0` the second decrement vanished
silently. On a row with copies left it did not.

### Measured, on the owner's own store

SKU 9197044, stored `live 3` against an export reading `2` — a real disagreement, from the
2026-09-07 export. The same two acts, run both ways against a copy of the real store:

| | reconcile → mark sold | mark sold → reconcile |
|---|---|---|
| **before** | `live 1` | `live 2` |
| **after** | estimate **1** | estimate **1** |

**The order decided the answer, and now it does not.** A second identical reconcile corrects
nothing, both before and after.

### The ruling

**`live` holds the export's reading and nothing else.** `sold_here` counts copies sold here
since that reading, `sold_here_at` dates the newest of them, and the figure every screen draws
is `live_estimate` — the difference, floored. `reconcile --live` **clears** the counter when it
adopts a reading taken after the sales, instead of racing it.

**This implements D7's ordering rather than reversing it.** D7 defends the decrement in as many
words — *"holding the count back until a join makes the app disagree with the shelf the
operator is standing in front of"* — and that is a rule about **when** the figure drops, not
about which field it drops in. The derived estimate drops on the same request, with no join in
between. D7 wanted the screen to agree with the shelf; it never required corrupting the
export's reading to get there, and that sentence in D7 is kept verbatim because it is the
argument this change is measured against.

### Why the counter needs its own stamp

`sold_here_at` is not decoration. The restamp being removed was the **only** thing standing
between a sale and a re-join: `cli/cmd_join.py` re-reads the run's RECORDED export, whose mtime
is its fetch time — measured at fifteen minutes before its own emit — so **an export fetched before a sale and read after it is the ordinary "Join again" press.** Without a stamp on the
counter that file is newer than `live_as_of`, clears a counter it knows nothing about, and the
sale is gone. `sales_pending` is `live_reading`'s sibling and answers for the counter what
`live_reading` answers for the figure, so `_copies_out` and `observe_live` cannot disagree
about one file.

**It is all-or-nothing**, because one stamp cannot split a file that landed between two sales;
a file that cannot be shown newer than the newest counted sale clears none of them, and the
estimate errs low — D7's direction.

**And its stampless case goes the opposite way from `live_reading`'s**, which is the design in
one line: an undateable file still wins the FIGURE (D8 and D11's authority) and still cannot
cancel a sale (a reading that cannot be placed in time cannot be shown to postdate one).

### A fourth verdict, and the early return that could not move

`observe_live` gained `CLEARED` — a reading that moved no copies and still wrote. It is
distinct from `ADOPTED` because three callers read these words and every one would say
something false with it: the reconcile would report "settled N listing(s)" beside "0 copies
corrected", `cmd_join` would run a staged drawdown of zero, and `_settlement`'s preview would
have no word for a write it must promise.

**The early equality return was narrowed, not moved**, and that is the subtlety. "Equal figure,
whatever the age" is what keeps a second `reconcile --live` over one file a no-op; moving it
past arbitration would turn it into `KEPT`, because ties go to the store — the same file read
twice would report itself outranked.

### What it closed that was accepted in writing

`server/capture_server.py` declined this design explicitly: *"the alternative is recording a
per-sale delta somewhere in order to reverse it exactly, which is a fourth thing the store
would have to explain for a number the export overwrites anyway."* Two things changed since.
The number the export "overwrites anyway" turned out to be the same number the sale was
writing; and D87's amendment dated the readings, so an export overwrites it only where it is
NEWER — which a sale was arranging by forging a reading time. **The drift that paragraph accepted — a decrement lost to the floor, returned by a later undo, leaving the estimate one high — is closed by the same move**, because the floor now lives on the derived value and on
nothing stored.

`bump` refuses `LIVE` outright. Its one caller was the sale, and leaving the expression
callable with a docstring explaining how to move `live` with it is how the next session puts
the defect back.

### What did not move

**D34's `release` is untouched, deliberately.** It is a rare, acknowledged, budgeted correction
with its own screen and receipt, bounded by the calling box's own copies, and it is not part of
the sale/reconcile loop that caused the confusion. It restamps `live_as_of` and that is honest
there: the operator has just asserted, on their word, that TCGplayer is holding none of it.
**After this entry it is the only non-export writer of `live_as_of` in the tree.**

**The cap reads the estimate**, and `check_listing_commands` pins why: once an import has
landed and `join` has drawn `staged` to zero, `claim` is 0 and the estimate is the only arm of
`max(live, claim - sold)` that can refill a SKU after a sale. Reading the raw figure there
would silently retire D7's refill. Three figures stay on the raw reading on purpose — the map's
key set, the corroboration gate (a fact about the FILE), and the box-delete guards, where a
guard on a destructive operation takes the safe reading.

**Nothing needed a migration.** An absent key defaults to 0 through `Inventory.parse`'s filter
on `__annotations__` (D88), and **backfilling any non-zero value would have been the defect** —
sales before this field existed were already applied to `live`. Rows corrupted by the old
double-decrement repair themselves on the next reconcile newer than the corruption.

### On screen, both figures

The operator's ruling: the reading and the pending sales are both drawn, everywhere. The big
figure is the estimate; the split under it — `4 when read · 2 sold here since` — appears only
where something has sold, because a row of zeroes on 440 of 443 SKUs trains the eye past the
three that matter.

**Including the Fulfiller, and that was the operator's call over my objection.** I argued for
the estimate alone on his view — `docs/DESIGN.md` bans jargon there and D5 says he gets no vote
on owner-side bookkeeping — and was overruled. He gets one sentence in his own words: *"2
copies sold here since we last counted."* It clears the banned-word list, and it earns its
place: the count above it now moves the instant he pulls a card, and without the sentence the
number would change under him with no reason given.

**And every reading age moved from `Listing.at` to `live_as_of`.** `at` is stamped by every
writer of every field. Before this entry a sale genuinely was a fresh observation of `live`, so
reading `at` was defensible; after it, a sale touches `at` while observing nothing at all —
**the age would have got fresher exactly as the figure got staler.**

**What would reopen this**: an operator who wants a price or a quantity they assert here to
outrank what TCGplayer reports. This entry keeps the export as the authority on the figure and
this store as the authority only on what it has done since.

### Amended 2026-09-10 — the run file is frozen, so the reader is what floors it

**"Nothing needed a migration" was true of the STORE and false of the RUN FILE.** The half it
was false about put `NaN` on the pricing screen. The paragraph above is about
`Inventory.parse`'s filter on `__annotations__` (D88), which defaults an absent key to 0 on the
way out of SQLite. `cli/cmd_join.py` freezes a copy of the same record into
`runs/<n>/pricing.json`, `do_pipeline_pricing` serves that file through, and
**nothing on that path defaults anything.**

Measured on the owner's store, 2026-09-09: across the eight run directories, **171 of 171**
non-null `listing` objects carry no `sold_here` — every one, because all eight were joined on
2026-09-01/02 and this entry is dated 2026-09-07. The client subtracted `undefined`, and the
"Smite" row (SKU 9191230) of `runs/2026-09-02-box6-01` drew **`NaN live · read 8 days ago`** on
the screen where money is decided.

**`NaN` is the worst possible failure here and that is why the fix is a floor.** It is not
loud: it throws nothing, logs nothing, and fails no type. It propagates — every `Math.max`,
every subtraction, every comparison and every template literal downstream of it stays `NaN`
without complaint — and it renders as a word.

### The reader supplies the zero, not the route

**Two places could have supplied it and only one of them is the reader.** The route was the
tempting fix and is refused on three grounds:

**It could not do better than the constant anyway.** `sold_here` counts sales since a
particular reading. The store's counter counts since **the store's own** `live_as_of`; the run
file's `live` is a **frozen, older** reading. Pairing the two would subtract, from a stale
reading, every sale that a `reconcile --live` since the join has already subtracted — the exact
double-count `pricingSource.ts:asRow` already spends a paragraph refusing when it writes
`sold_here: 0` for a live-lens row, and that `cli/resolve.py:_copies_out` and `Listing.held`
each refuse in their own terms. So the honest server fill is `0`, which is the reader's answer
carried further from the reader.

**It would not be a floor.** A default on that route fixes one key on one route; the next field
added to a frozen record produces an identical defect at an identical cost. The guard belongs
where the arithmetic is, and the arithmetic is `cardState.ts:forSale` — a helper whose own
header already says it exists so the rule does not live in six places. It is now seven, and the
seventh — `Pricing.tsx:LiveCount`, which wrote the expression out rather than calling it — is
the copy that shipped the defect.

**`do_pipeline_pricing` composes exactly one thing and it is not this.** That handler's
docstring stakes out the boundary in as many words — it re-renders position labels because D58
makes a stored label wrong, and computes nothing else. A second composed value, invented rather
than derived, is a route acquiring an opinion about a record it is serving through.

### A type cannot catch this class, so the type stops claiming it can

`PricingSku.listing.sold_here` was declared `number` while 171 of 171 records lacked it.
**A declaration on a record read back off disk describes what the writer emits today**, and
every file written before a field existed contradicts it — silently, because the payload is
cast and not validated. It is `sold_here?: number` now, which made the compiler name the single
unguarded reader on the first run. `PricingPayload.written_at` is the same class and was
already declared this way; that is the precedent, not an exception.

**The sweep this came with found no second live case.** Every other optional wire number the
client does arithmetic on is honestly typed and therefore already `tsc`-guarded — `BoxRecord`'s
`on_hand ?? cards - sold - retired - moved`, `to_send`, `estimate_usd`, `cache_hits`. Of the
other four fields the eight stored `pricing.json` files disagree on, `copies_out` is read by no
client code, `nothing_to_add` is `??`-guarded, `over_cap` is boolean-coerced, and the
worklist route composes `over_cap` itself.

**What would reopen this**: a run file gaining a field the client must do arithmetic on where
absence and zero mean *different* things. `0` is right here only because a table written before
the counter existed genuinely recorded no sales-since — the difference is then the reading
itself, which is what the screen drew before this entry and correct as of the join.