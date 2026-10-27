# D87 — Reconcile is store-wide and writes live

**One full TCGplayer live export settles every SKU in the store, whatever run or box it came from, and reports both directions.** The owner's ruling, after D86, is that an export of the whole live inventory reconciles across every emit and box. It does so at any time.

**The asymmetry that made it cheap.** `cli/cmd_reconcile.py` scopes its diff to one run's `emitted_skus`. But the thing it diffs against was never run-scoped. `store/master.py:Listing` holds `pushed`, `staged` and `live` per SKU across every box and run. D7 says quantities are held against a SKU, not states a card wears. The scoping was a property of the command, not of the data.

### What it found, on the owner's own store

Measured against a real My Pricing export of 757 rows:

| | |
|---|---|
| SKUs with a listing record | 443 |
| **carrying pushed copies with `live: 0`** | **405** |
| `staged`, anywhere | 0 |
| SKUs over the 4-copy cap | 2, at `pushed: 6` |

Reconcile had effectively never run. `pipeline/join.py`'s cap arithmetic worked from `Total Quantity` in whatever export a run held. The store's own `live` contributed nothing. After the settlement, it sees 1,079 live copies where it saw 93.

### What it writes is `live`, and only `live`

It also clears `sold_here` where it adopts (D115). `pushed` stays the cumulative record and is never rewritten. The counter holds copies sold here since the reading. So when the reading moves, the counter clears with it. That is the counter's own definition, not a claim about TCGplayer. A reading the store outranks clears nothing. Neither does one whose figure merely agrees.

**`pushed` is cumulative, not outstanding.** It counts copies ever written into an import file. An import file holds the last delta only (D54). The per-run reconcile is the only thing that draws it down. On a store that never reconciled, `pushed` is the only record of what was sent. Rewriting it destroys that. A settlement that wrote `pushed` was tried first and was wrong twice over.

**`cli/resolve.py:_copies_out` already corrects a stuck `pushed`.** Its comment says the ceiling is physical: TCGplayer cannot hold more copies than were sent and not sold. The arithmetic was missing a real `live`, which nothing in this repo had ever written. Writing it is the fix.

**The ledger's own `live` is a stale observation, not a second belief.** Adding it to `pushed` looks principled. `LISTING_STAGES` partitions the sent copies. But it is false of this data: 32 of the 38 SKUs carrying a legacy `live` would then claim more copies than were ever captured. The two describe the same copies at different moments. The export supersedes the ledger.

**The settlement must reach the cap.** `_copies_out` read `live` from the export's `live_by_sku` alone, and refused the store's, because nothing could tell which of two readings was newer (D59: "nothing here knows which of the two readings is the newer one"). So `--live --write` moved 1,079 copies the cap arithmetic never saw. `cli/cmd_join.py` also set `live` from whatever export the join was handed. Run `2026-09-01-box3-01`'s recorded export was fetched fifteen minutes before that run was emitted. Its `Total Quantity` was blank for every SKU it had just listed, and `parse_quantity('')` read 0. "Join again" on `#/runs` with the picker left alone was the ordinary path. It took a copy of the store from 1,072 live copies over 406 SKUs to 700 over 266.

The fix is D59's amendment. `Listing.live_as_of` dates every reading. `Listing.live_reading` arbitrates the cap, and `Listing.observe_live` arbitrates the write. The join and reconcile reports name what they kept. An uploaded export carries `File.lastModified`, so its stored copy is dated to the file, not to the upload. A settlement row was written before the field existed. `Listing.from_record` reads its `at` as the observation time at the parse. Absent is legacy. Null is a record nothing has read `live` for. The two are told apart nowhere else.

**Idempotence separates the two designs.** A settlement that rewrites `pushed` destroys the record it read, so its second pass answers a different question. Measured, it gave 126 unexplained on the first pass and 120 on the second, over an unchanged store. Writing only `live` gives 55 both times, and 0 corrections on the second.

### The residual is a sentence, never an adjustment

**55 copies across 32 SKUs** were sent, are not live, and no card is marked sold. That is genuinely ambiguous. The copies may have sold and gone unmarked, been pulled by hand, or been rejected by the portal. This command names them and changes nothing.

The owner's order list settles what it is. The owner estimated under 25 cards pending. The ledger said 55, and both were right about different things. `Ready to Ship` is 2 orders awaiting shipment. The 55 is every copy that sold and was never marked, shipped or not. The corroboration is arithmetic. The first emit was 22 August, so every pushed copy left inside that window. The window holds 93 non-cancelled orders against 123 departed copies: 1.32 cards per order.

**It moves quantities and never cards (D7).** Which physical copy sold is deliberately unrecorded. Every unsold copy is equally sellable, and the export could not say anyway. So this marks nothing `sold`. That is the operator's act on `#/inventory`.

### The other direction, which a per-run reconcile cannot have

- **33 SKUs live at TCGplayer this store has never seen**, 61 copies: sealed product, accessories, and singles listed before banchi. Reported and never touched.
- **10 SKUs TCGplayer holds more of than were ever sent from here.** Brutalizer is at 8 live against 5 copies ever captured. Left alone, because this pipeline did not put them there.

`seen` is deliberately wider than the listing ledger. It holds every SKU any card carries. A withheld (D86) or not-yet-emitted card has a SKU and no listing. Judging against the ledger alone would accuse the operator of listing it outside banchi the moment it went live.

### Reachable, and where

`#/runs`, under the run panel. That screen's lede names the four commands. This is the fourth, in the shape that is not run-scoped, and the panel says so. Not `#/inventory`. That is where a card's state changes, and this changes none.

**Two presses, and the first writes nothing.** D33's gate pointed at the ledger rather than at the money. `prices adopt`'s reason is that it moves the quantities the cap arithmetic reads, over every SKU at once. The settle control is absent until a preview has answered. The same bytes are sent twice rather than re-picked.

### What would reopen this

*Line-item attribution.* This settles quantities and cannot say which copy of a SKU sold, because the order list is order-level. `server/order_transport.py` (D69) already fetches this account's own orders, authenticated. If it can reach line items, the residual stops being ambiguous. The reconcile could then mark cards sold. That would make D7's "quantities, not copies" a question worth re-arguing.

*A `staged` that stays empty.* It is 0 for all 443 SKUs, and the only writer is the per-run reconcile. If the store-wide path is the one that gets used, `staged` is a stage nothing occupies. The ledger is then two counts and a record.
