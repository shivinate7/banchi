## D-a-record-price-postings — Every posted price is recorded, and the row is never touched again

**The gap, measured on the owner's real store, 2026-09-20.** The owner cannot answer "what
have I asked for this card over time." The `events` ledger carries 143 `pushed` lines. None
of them names a price. The payload is `at`, `event`, `position`, `run`, `sku`.
`inventory/prices.json` (D86) is newest-wins by design. Each repricing overwrites the last.
It answers only "what is the price now." Seven `inventory/markdowns/` folders record what a
reprice worklist PROPOSED. That is only for runs that went through that path. So the history
is unrecoverable for nearly every SKU today. It is lost further every time a price is
posted. It is being fixed now, on the owner's word. It is perishable: every day it is not
built is a day of postings this table will never recover.

**The fix records the price at the moment it is decided, on the paths that decide it.**
`pipeline/tcgcsv.py`'s `set_writable` is the one function that ever composes a `TCG
Marketplace Price` cell. It is reached from three places. `pipeline/join.py:import_rows`
serves a single run's `emit`. `pipeline/merge.py:import_rows` serves a merged send's
`emit`. `pipeline/reprice.py:import_rows` serves `reprice apply`. All three were checked.
There is no fourth writer. `store/postings.py`'s `Postings.record()` is called once per SKU
at the exact point each caller already decides a row reached a file. That point is
`cli/cmd_emit.py`'s existing `pushed` gate for both emit paths, and `reprice apply`'s
`--write` gate for the third. It is never earlier, and never for a price only proposed.

**The table is `price_postings`, one row per SKU per press, and it is never an upsert.**
`store/pricearchive.py` (D219) and `store/readings.py` (D189) are the same shape one
register over. Both are an append-only table keyed by subject and time, with an accounting
of what a press wrote. Both are correctly `upsert`s, because both cache a number a live
source can answer again. A posted price has no second copy. The number is composed once, at
the instant it is written into a CSV cell. Once that byte leaves for TCGplayer, nothing is
left to ask what it used to be. So this table is shaped like `events` instead:
`id INTEGER PRIMARY KEY AUTOINCREMENT`, one `INSERT`, no `UPDATE` and no `DELETE` statement
anywhere in the module. It never goes through `store/rows.py`'s `Rows`/`TableSpec`
framework. That framework's flush is delete-then-upsert BY KEY, exactly the operation this
table must never perform. `scripts/price-postings-selftest.py --mutate-to-upsert` proves the
distinction. It rewrites `append_postings` into a real upsert keyed on `sku`, by one literal
string replacement. The same suite that passes 13/13 against the real code goes red under
that mutation.

**The grain is the SKU, never a card or a copy (D212).** Every copy of a SKU is fungible.
One press writes one cell for the whole SKU, so a posting is one row per SKU per press.

**What is recorded, and what is not.** A row exists only for a price that reached a file a
press wrote to disk. A proposal an operator edited and discarded posts nothing. A run
refused before a byte was written posts nothing. `store/postings.py`'s `.record()` is simply
never called for either case. `source` names which press wrote the row: `emit`,
`emit-merged`, or `reprice`. `run` names the run or the markdown folder that decided it.
`replaced` carries the price a posting is known to have superseded. It is filled in only
where the caller already has that value in hand. `reprice apply` always does — the
worklist's own `was`. That is the case the owner asked about by name: a SKU priced a second,
third or fourth time. `emit` tracks no prior asking price at all, so its rows carry
`replaced=None` rather than a guess.

**Recoverability of history from what already survives is close to nothing.** That is the
argument for landing this now. Measured read-only against the owner's real
`inventory/store.sqlite` (`scripts/price-postings-recovery.py`): the 143 `pushed` events name
no price at all. Zero prices are recoverable from the ledger. Of seven reprice markdown
folders, only one was ever actually applied, with `receipt.txt` and `import.csv` both
present. That one names 342 SKUs' prices, out of 914 SKUs the store has ever committed a
card to. That figure is one later snapshot, not a history. Every SKU's very first posted
price is unrecoverable for all 914 of them. `pushed` carries no price, and nothing earlier
was ever applied. This store's real price history is gone before this table starts keeping
it.

**Not reachable from a screen, on purpose.** The owner's ruling is to record first, and
build the view once there is something to look at. No route, no client function, and no UI
reads this table. This is not a route left unfinished. It is a store-layer table with no
route at all yet. It is named here so a future session builds the view, rather than
re-discovering that the table exists.
