## D109 — A price belongs to a listing

**Built on the owner's instruction, after the measurement settled the question.** The operator asked two things. Is pricing hampered by its coupling to inventory and runs? Can Banchi act as a courier for prices it did not originate?

**The measurement, on the owner's live export** (759 rows, 387 live):

| refused as | SKUs | copies | asking value | share |
|---|---|---|---|---|
| `too_young` | 184 | 398 | $304.94 | 2.4% |
| **offered** | 100 | 363 | $268.79 | 2.1% |
| `at_floor` | 52 | 135 | $49.11 | 0.4% |
| **`not_this_store`** | **28** | **82** | **$12,153.95** | **94.5%** |
| `sold_recently` | 20 | 31 | $69.10 | 0.5% |
| `held` | 3 | 6 | $12.86 | 0.1% |

**232 of 387 live SKUs were refused on a card-table fact, not a price.** That is 60% of them, carrying 97.4% of the asking value. The rule reached 2.1% of the operator's own book.

### What was already decoupled, and what was not

The answer was never coupled. `pipeline/corpus.py` is keyed by SKU. Its header says *"NOTHING HERE READS THE STORE OR THE CATALOG."* D86 moved the pricing answer out of run directories. A price is a property of the SKU, not of the drawer a photograph was taken in. What stayed coupled was every path that reached that answer.

**Two refusals did the damage. They are different mistakes.**

`NOT_THIS_STORE` was **membership**. The check is `if sku not in owned_since: refuse`. It fired third, before asking, market, basis or rule were consulted. D103 characterized those rows as *"Card Sleeves, Playmats, a YuGiOh row"*. That was true when written and is false now. The set holds a $7,000 Kai'Sa. It also holds a Surging Sparks Booster Box Case asking **$155 below market on a $2,000 item**. It holds a Bard, Mercurial asking **218% above** market, not selling. These are two live money problems, drawn on the operator's screen and untouchable.

`TOO_YOUNG` was **the wrong clock**. D100 ranked staleness by how long the CARD had been OWNED. It did so because `Listing` had no first-listed stamp, and `live_as_of` was null on all 443 records. Every report named the substitution in its header. But the operator's oldest capture is younger than any sane window. So the term measured when this project got a camera. It did not measure how long anything had been listed.

### The ruling

**A price is a fact about a listing. A card record is not a licence to have one.** What a photograph buys is a position and an image. Neither is consulted to decide what a card costs. So membership stops being a refusal and becomes drawn evidence (`Candidate.held_here`). `UNPRICEABLE_CODES` narrows to `SOLD_OUT` alone. That is a fact about the LISTING, which is what that table is for. When nothing is live, there is no live listing for a price to edit.

**The store remembers its whole live book, not just the part it photographed.** `store/master.py:Listing` gains two fields:

- **`first_seen_live`**: the earliest export observed holding the SKU. It is MONOTONE: earliest wins, nothing overwrites it, and a reading with no parseable stamp writes nothing. This is the real term D100's proxy stood in for. It is available for a SKU no card here carries, as readily as for one photographed in a box.
- **`priced_at`**: when this store last set a price. **The stamp only, never the figure.**

`cli/cmd_reconcile.py` now WRITES the rows it previously only reported. Before this landed, **0 of 443 listing records had no card behind them.** The export carried 28 live SKUs that did. The store had no memory of its live book beyond what a camera had seen. So nothing could date a listing. Nothing stopped a rule marking the same one down on every pass, and a copy selling was invisible.

### Why the figure is not stored: the courier design

Once a price is published, it is live at TCGplayer. The next export reads it straight back as `asking`. **Keeping a copy here would be a second money truth, able to disagree with the first on the one field a buyer can see.** The export cannot report whether THIS store made the change. The markdown ratchet needs that fact, so a rule cannot cut the same card every time the screen opens. So Banchi records that it acted. TCGplayer remains the price of record.

The corpus is not seeded from the export. `corpus.stamp_answers` is diff-based. Seeding 341 readings would re-date all of them, and the next `reprice list` would refuse every one as `priced_recently`. The only escape is `--again`, which is global. The ratchet would then have two settings: refuse everything, or protect nothing. It would stop meaning *"this store decided a price recently"*. It would mean *"TCGplayer's cell changed recently."* Nothing would fail. The report would just be wrong in words.

### What did NOT move

**The live cap stays coupled to positions. None of its arithmetic changed.** `pipeline/join.py:add_to_quantity` spends `live_cap - copies_out`, bounded by `len(uncommitted_positions)`. No export column carries how many copies are in a drawer. So **this widens what may be RE-PRICED, never what may be LISTED.** `pipeline/reprice.py` writes `ADD_TO_QUANTITY = 0` as a module constant. `check_quantities_zero` asserts it over the worklist and the import bytes. `server/tcg_import.py:_check` refuses the whole file on a non-zero quantity. Three guards, unchanged. The road from *I own this card* to *it is for sale* still runs through a photograph.

**The screen stops offering what the pipeline will not honour.** `GET …/table` has shipped `unpriceable` since D103, with the comment *"so the row can refuse the field rather than let the operator type a price the apply will throw away"*. Nothing in `app/src` read it. A locked row drew a live input. `pushable` counted it, the corpus write landed, and only the receipt named the refusal. That is D101's defect, verbatim. It is fixed here, not left standing on a narrower set.

**The lens opens empty.** `PricingSource.proposes` is true for a run and false for a lens. The reason matches `repartition`: what an untouched row MEANS differs. A run's rows are not listed yet, so the rule's price is the answer until overridden. A lens's rows are already live at a price somebody chose. The rule speaks about 243 of 387 at a 7-day window. A filled field would turn one bulk press into 243 live price changes. The figure is drawn as a placeholder. One keystroke or one preset away, and nothing moves that the operator did not move.

**What would reopen this:** an operator who wants a typed price here to be authoritative over what TCGplayer reports. That is a genuine want. It is also the point where the figure would have to be stored beside the stamp and arbitrated. D87's "newer wins" does not generalise to it. `live` is a quantity both parties observe. An asking price is our instruction, which they execute. Those are not two readings of one fact.

**The record it creates could not be settled when the listing sold out (amended).** Every record this entry writes carries `pushed = 0`. That is correct, because this pipeline sent none of it. `pipeline/livecheck.py` bucketed on `claim`. A row at `claim == 0` reached `beyond` only `if live > 0`, so one reading **zero** fell into no bucket at all. `cli/cmd_reconcile.py` builds `settling` from `agreed + unexplained + beyond`. So `observe_live` was never called, and the stored reading stood forever.

**It took two exports to see, which is why it shipped.** The first records the listing. The second is where it goes wrong. On the owner's own book, that is 47 live SKUs holding 127 copies, 26 of them one booster pack. The first `--write` would have armed every one of them.

**`row.ledger_live > 0` is the condition, not `if True`.** A SKU neither side has anything on, reading zero, is genuinely nothing to say. It still falls through. What earns a line is the store believing something the export contradicts. `beyond`'s printed sentence covers both directions now. It said "holds more than this pipeline ever sent", which is false of a row at zero.
