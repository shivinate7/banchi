## D109 — A price is a fact about a listing, and the store remembers listings it never photographed

**Built 2026-09-06, on the owner's instruction, after four agents were set against the question and the measurement settled it.** The operator asked whether pricing was being hampered by its
coupling to inventory and runs — *"i feel maybe we're hampering banchi's pricing capability by
tying it to only our inventory/runs"* — and, separately, whether Banchi could act as a courier
for prices it did not originate: *"frankly if banchi could be a courier it would be nice."*

**The measurement, on the owner's own live export of 2026-09-06** (759 rows, 387 live):

| refused as | SKUs | copies | asking value | share |
|---|---|---|---|---|
| `too_young` | 184 | 398 | $304.94 | 2.4% |
| **offered** | 100 | 363 | $268.79 | 2.1% |
| `at_floor` | 52 | 135 | $49.11 | 0.4% |
| **`not_this_store`** | **28** | **82** | **$12,153.95** | **94.5%** |
| `sold_recently` | 20 | 31 | $69.10 | 0.5% |
| `held` | 3 | 6 | $12.86 | 0.1% |

**232 of 387 live SKUs — 60% of them, carrying 97.4% of the asking value — were refused on a fact that came out of the card table rather than out of a price.** The rule reached 2.1% of
the operator's own book.

### What was already decoupled, and what was not

The ANSWER was never coupled. `pipeline/corpus.py` is SKU-keyed, and its own header says
*"NOTHING HERE READS THE STORE OR THE CATALOG."* D86 moved the pricing answer out of run
directories precisely because a price is a property of the SKU and not of the drawer a
photograph was taken in. What stayed coupled was every path that REACHED that answer.

**Two refusals did the damage, and they are different mistakes.**

`NOT_THIS_STORE` was **membership** — `if sku not in owned_since: refuse`, fired third, before
asking, market, basis or rule were consulted at all. D103 characterized those rows as
*"Card Sleeves, Playmats, a YuGiOh row"*, and that reading was true when it was written and
false by 2026-09-06: the set now holds a $7,000 Kai'Sa, a Surging Sparks Booster Box Case
asking **$155 below market on a $2,000 item**, and a Bard, Mercurial asking **218% above**
market and not selling. Two live money problems, drawn on the operator's screen and
untouchable.

`TOO_YOUNG` was **the wrong clock**. D100 ranked staleness on how long the CARD had been
OWNED, because `Listing` had no first-listed stamp and `live_as_of` was null on all 443
records — and every report named the substitution in its own header, honestly. But the
operator's oldest capture is 2026-08-23, so at any sane window the term was measuring **when this project got a camera**, not how long anything had been listed.

### The ruling

**A price is a fact about a listing, and a card record is not a licence to have one.** What a
photograph buys is a position and an image; neither is consulted to decide what a card costs.
So membership stops being a refusal and becomes drawn evidence (`Candidate.held_here`), and
`UNPRICEABLE_CODES` narrows to `SOLD_OUT` alone — a fact about the LISTING, which is what that
table is for. There is no live listing for a price to edit when nothing is live.

**And the store remembers its whole live book, not just the part it photographed.**
`store/master.py:Listing` gains two fields:

- **`first_seen_live`** — the earliest export observed holding the SKU. MONOTONE: earliest
  wins, nothing overwrites it, and a reading with no parseable stamp writes nothing. This is
  the real term D100's proxy was standing in for, and it is available for a SKU no card here
  carries as readily as for one photographed in a box.
- **`priced_at`** — when this store last set a price. **The stamp only, never the figure.**

`cli/cmd_reconcile.py` now WRITES the rows it previously only reported. Measured before this
landed: **0 of 443 listing records had no card behind them, while the export carried 28 live SKUs that did.** The store had no memory of its own live book beyond what a camera had seen —
so nothing could date a listing, nothing stopped a rule marking the same one down on every
pass, and a copy selling was invisible.

### Why the figure is not stored, which is the courier's whole design

Once a price is published it is live at TCGplayer, and the next export reads it straight back
as `asking`. **Keeping a copy here would be a second money truth able to disagree with the first on the one field a buyer can see.** What the export cannot report is whether THIS store
made the change — which is exactly what the markdown ratchet needs so a rule cannot cut the
same card every time the screen is opened. So Banchi records that it acted, and TCGplayer
remains the price of record.

This is also why the corpus is not seeded from the export, which was the tempting version.
`corpus.stamp_answers` is diff-based, so seeding 341 readings would re-date all of them and
the next `reprice list` would refuse every one as `priced_recently`; the only escape is
`--again`, which is global. The ratchet would have two settings — refuses everything, or
protects nothing — and would silently stop meaning *"this store decided a price recently"* and
start meaning *"TCGplayer's cell changed recently."* Nothing would fail. The report would just
be wrong in words.

### What did NOT move, and this is the load-bearing half

**The live cap stays coupled to positions, and none of its arithmetic changed.**
`pipeline/join.py:add_to_quantity` spends `live_cap - copies_out` bounded by
`len(uncommitted_positions)`, and no export column carries how many copies are in a drawer.
So **this widens what may be RE-PRICED and never what may be LISTED**: `pipeline/reprice.py`
writes `ADD_TO_QUANTITY = 0` as a module constant, `check_quantities_zero` asserts it over the
worklist and the import bytes, and `server/tcg_import.py:_check` refuses the whole file on a
non-zero quantity. Three guards, unchanged. The road from *I own this card* to *it is for sale*
still runs through a photograph.

**The screen stops offering what the pipeline will not honour.** `GET …/table` has shipped
`unpriceable` since D103 with the comment *"so the row can refuse the field rather than let the
operator type a price the apply will throw away"* — and **nothing in `app/src` ever read it**.
A locked row drew a live input, `pushable` counted it, the corpus write landed, and only the
receipt named the refusal. That is D101's defect verbatim, and it is fixed here rather than
left standing on a narrower set.

**And the lens opens empty.** `PricingSource.proposes` is true for a run and false for a lens,
for the same reason `repartition` splits: what an untouched row MEANS differs. A run's rows are
not listed yet, so the rule's price is the answer until overridden. A lens's rows are already
live at a price somebody chose, and the rule speaks about 243 of 387 at a 7-day window — a
filled field would turn one bulk press into 243 live price changes, which is the envelope
arriving pre-signed. The figure is drawn as a placeholder: one keystroke or one preset away,
and nothing moves that the operator did not move.

**What would reopen this**: an operator who wants a price they typed here to be authoritative
over what TCGplayer reports — a genuine want, and the point at which the figure would have to
be stored beside the stamp and arbitrated. D87's "newer wins" does not generalise to it: `live`
is a quantity both parties observe, and an asking price is an instruction of ours as executed
by them, which are not two readings of one fact.

**THE RECORD IT CREATES COULD NOT BE SETTLED WHEN THE LISTING SOLD OUT (amended 2026-09-08).** Every record this entry writes carries `pushed = 0` — correct, because this pipeline sent none of it — and `pipeline/livecheck.py` bucketed on `claim`: a row at `claim == 0` reached `beyond` only `if live > 0`, so one reading **zero** fell into no bucket at all. `cli/cmd_reconcile.py` builds `settling` from `agreed + unexplained + beyond`, so `observe_live` was never called and the stored reading stood forever.

**It took two exports to see, which is why it shipped.** The first records the listing; the second is where it goes wrong. On the owner's own book that is 47 live SKUs holding 127 copies — 26 of one booster pack — every one of which the first `--write` would have armed.

**`row.ledger_live > 0` is the condition, and it is not `if True`.** A SKU neither side has anything on, reading zero, is genuinely nothing to say and still falls through; what earns a line is the store believing something the export contradicts. `beyond`'s printed sentence covers both directions now — it said "holds more than this pipeline ever sent", which is false of a row at zero.