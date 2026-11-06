## DEBT121 — a hold take-off writes a price with no posting

**What.** A hold take-off row writes the live price into a send's file, and `price_postings` (D243, every posted price is recorded once) gets no row for it.

**Harm.** The price history misses every hold take-off. D243 says that history cannot be recovered later. The master-set take-off records its row (`server/send_routes.py`'s `_master_take_off`), so the two take-off paths disagree.

**Where.** `cli/cmd_emit.py`'s `_takeoffs` builds the `_Take` rows, and both emit paths write them into the file. `_record_prices` records only the price `changes`, and the copy gates record only rows with copies, so a `_Take` row reaches no `Postings.record()`.

**Fix, when taken.** Record each `_Take` row with source `postings.TAKE_OFF` and `replaced` set to its price, at the same store write that claims it (`_claim_or_refuse`). Add a case to the hold take-off check (`check_send_hold_takes_off`).

**Measured.** Unmeasured: how many hold take-offs the owner's store has sent.
