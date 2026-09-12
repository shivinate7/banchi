## D87 — The reconcile is store-wide, and what it writes is `live`

**One full TCGplayer live export settles every SKU in the store, whatever run or box it came from, and reports both directions.** Built 2026-09-02 on the owner's instruction, after D86 moved the pricing answer into one corpus: *"if you've tracked what all's been emited, then if i ever get an export of my entire live tcgplayer inventory, it should be able to auto reconcille across emits/boxes of any times."*

**The asymmetry that made it cheap.** `cli/cmd_reconcile.py` scopes its diff to one run's `emitted_skus`, but the thing it diffs against was never run-scoped: `store/master.py:Listing` holds `pushed`/`staged`/`live` **per SKU across every box and run**, and D7 amended says so — *"quantities held against a SKU rather than states a card wears"*. The scoping was a property of the command, not of the data.

### What it found, on the owner's own store

Measured 2026-09-01 against a real My Pricing export, 757 rows:

| | |
|---|---|
| SKUs with a listing record | 443 |
| **carrying pushed copies with `live: 0`** | **405** |
| `staged`, anywhere | 0 |
| SKUs over the 4-copy cap | 2, at `pushed: 6` |

**Reconcile had effectively never run.** So `pipeline/join.py`'s cap arithmetic was working off `Total Quantity` from whatever export a run happened to hold, with the store's own `live` contributing nothing at all. After the settlement it sees **1,079 live copies where it saw 93**.

### What it writes is `live`, and only `live` — which is smaller than it first looks

**Amended 2026-09-07 (D115): it also clears `sold_here` where it adopts.** That is not a second belief and it does not widen this heading's argument — `pushed` is still the cumulative record and is still never rewritten. The counter holds copies sold here SINCE the reading, so "since the reading" stops meaning anything the moment the reading moves; clearing it is the counter's own definition rather than a new claim about TCGplayer. A reading the store outranks clears nothing, and neither does one whose figure merely agrees.

The first build settled `pushed` too, drawing it down by what the export accounted for. That was wrong twice over and the second pass is what proved it.

**`pushed` is CUMULATIVE, not outstanding.** It counts copies ever written into an import file, an import file holds the last delta only (D54), and the per-run reconcile is the only thing that draws it down. On a store that never reconciled it is *the only record of what was sent*. Rewriting it destroys that.

**And `cli/resolve.py:_copies_out` already corrects a stuck one**, in its own words: *"THE CEILING IS PHYSICAL, AND IT IS WHAT CORRECTS A STUCK `pushed` … it cannot be true that TCGplayer holds more copies than we sent and have not sold."* What that arithmetic was missing is a real `live` — **which nothing in this repo has ever written**. Populating it is the whole fix.

**The ledger's own `live` is a stale observation, not a second belief.** Adding it to `pushed` looked principled — `LISTING_STAGES` partitions the sent copies — and is false of this data: **32 of the 38 SKUs carrying a legacy `live` would then claim more copies than were ever captured.** The two describe the same copies at different moments, so the export supersedes it.

**Amended 2026-09-02: the settlement was not wired to the cap, and the next re-join overwrote it.** `_copies_out` read `live` from the export's `live_by_sku` alone and refused the store's — its comment cited D59's *"nothing here knows which of the two readings is the newer one"* — so `--live --write` moved 1,079 copies the cap arithmetic never saw, and "the whole fix" above was a claim about a field nothing downstream read. And `cli/cmd_join.py` set `live` from whatever export the join was handed: run `2026-09-01-box3-01`'s recorded export was fetched fifteen minutes BEFORE that run was emitted, `Total Quantity` blank for every SKU it had just listed and `parse_quantity('')` reading 0, and "Join again" on `#/runs` with the picker left alone — the ordinary path — took a copy of the store from 1,072 live copies over 406 SKUs to 700 over 266. Closed by D59's amendment of the same day: `Listing.live_as_of` dates every reading, `Listing.live_reading` arbitrates the cap and `Listing.observe_live` the write, the join and reconcile reports name what they kept, and an uploaded export carries `File.lastModified` so its stored copy is dated to the file rather than to the upload. A settlement row was written before the field existed, and `Listing.from_record` reads its `at` as the observation time at the parse — absent is legacy, null is a record nothing has read `live` for, and the two are told apart nowhere else.

**Idempotence is the test that separates the two designs.** A settlement that rewrites `pushed` destroys the record it read, so its second pass answers a different question — measured, 126 unexplained on the first pass and 120 on the second over an unchanged store. Writing only `live` gives 55 both times, and 0 corrections on the second.

### The residual is a sentence, never an adjustment

**55 copies across 32 SKUs** were sent, are not live, and no card is marked sold. That is genuinely ambiguous — sold and unmarked, pulled by hand, or a row the portal rejected — and this command names them and changes nothing.

**The owner's order list settled what it is.** They estimated *"under 25 cards"* pending; the ledger said 55, and both were right about different things. `Ready to Ship` is **2 orders** awaiting shipment. The 55 is every copy that sold and was never marked, shipped or not. The corroboration is arithmetic: the first emit was 2026-08-22, so every pushed copy left inside that window; the window holds **93 non-cancelled orders** against **123 departed copies** — 1.32 cards per order.

**IT MOVES QUANTITIES AND NEVER CARDS (D7).** Which physical copy sold is deliberately unrecorded — every unsold copy is equally sellable and the export could not say anyway — so this marks nothing `sold`. That is the operator's act on `#/inventory`.

### The other direction, which is the half a per-run reconcile cannot have

- **33 SKUs live at TCGplayer this store has never seen**, 61 copies: sealed product, accessories, and singles listed before pkmnscan. Reported and never touched.
- **10 SKUs TCGplayer holds MORE of than were ever sent from here** — Brutalizer at 8 live against 5 copies ever captured. Left alone: this pipeline did not put them there.

`seen` is deliberately **wider than the listing ledger** — every SKU any card carries. A withheld (D49) or not-yet-emitted card has a SKU and no listing, and judging against the ledger alone would accuse the operator of listing it outside pkmnscan the moment it went live.

### Reachable, and where

`#/runs`, under the run panel. That screen's own lede names the four commands; this is the fourth, in the shape that is not run-scoped, and the panel says so. Not `#/inventory`: that is where a card's state changes and this changes none.

**Two presses, and the first writes nothing** — D33's gate pointed at the ledger rather than at the money, and `prices adopt`'s reason: it moves the quantities the cap arithmetic reads, over every SKU at once. The settle control is **absent** until a preview has answered, and the same bytes are sent twice rather than re-picked.

### What would reopen this

*Line-item attribution.* This settles quantities and cannot say which copy of a SKU sold, because the order list is order-level. `server/order_transport.py` (D69) already fetches this account's own orders authenticated; if it can reach line items, the residual stops being ambiguous and the reconcile could mark cards sold — which would make D7's "quantities, not copies" a question worth re-arguing rather than a settled one.

*A `staged` that stays empty.* It is 0 for all 443 SKUs and the only writer is the per-run reconcile. If the store-wide path is the one that gets used, `staged` is a stage nothing occupies and the ledger is really two counts and a record.
