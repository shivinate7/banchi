## D-a-card-row-ledger-fallback — A card row that refuses retries the ledger's own row

`pipeline/pricearchive.py:rows_from_store` prefers the `cards` row over the order
ledger's row whenever a SKU has both. That default is right. The card row carries the
operator's own stored facts (D172's own name-first argument). The preference was
unconditional. It lost real coverage when the card row was the worse of the two.

### Measured on the owner's real store, run 3, 2026-09-20

Run 3 printed 20 refusals. 18 were card-derived rows, not ledger-derived. Two causes,
both real, both traced to specific SKUs.

**A stored number with no denominator.** `Bulbasaur` `001` in `ME01: Mega Evolution`
refused. The mirror carries that set. It carries `Bulbasaur - 001/132` with number
`001/132`. `pipeline/join.py:number_index_key` strips leading zeros per digit run. A bare
`001` folds to `1`, never `1/132`. That is a genuine miss against the number index. It is
not a bug in the fold. The name rung then finds two products that fold to `BULBASAUR`.
One is the plain `001/132`. The other is a `133/132` secret rare. D35 already names this
pattern: a product's own name embeds its number. `ProductIndex.find` refuses rather than
guessing.

**A stored number carrying a separator.** `Twisted Fate` `OGN · 200/298` in `Origins`
refused. That SKU's own order line carries a clean form instead:
`Riftbound League of Legends Trading Card Game - Origins: Twisted Fate, Gambler - #200/298 - Near Mint Foil`.
The stored number's typed prefix never appears in the mirror's own number cell. Neither
the number rung nor the name rung matches.

**In both cases the ledger already holds a row that would resolve.** The order line's own
`name` carries the clean number and name the mirror actually indexes. It is the same
grammar D231 already parses for sealed-product widening.

### THE FIX: RETRY, NEVER SUBSTITUTE

`cards` stays the preferred source. That choice is unconditional, for the whole subject
list. Nothing about `rows_from_store`'s primary return value changes.

`sweep()` gains one narrower move. Suppose `Market.readings_for_rows` refuses a SKU whose
row came from `cards`. Suppose a ledger-derived row for that same SKU also exists.
`sweep()` then retries that SKU against the ledger row. Only then does it report a
refusal.

`rows_from_store` gains a `fallback_rows` out-parameter. It is filled only when `market`
is given. It carries a ledger-derived row for every card-covered SKU the ledger can also
answer for. It is built by `_ledger_export_rows` — the same machinery
`ledger_subject_rows` already uses for its own, opposite-direction widening. Building it
costs nothing new. `Market.groups` is a cached, whole-category read, already paid for once
per distinct Product Line the ledger has ever sold.

`sweep()` retries only the SKUs its first pass refused. It retries only among those
`fallback_rows` names. A SKU with no ledger line keeps its original refusal, unchanged. A
SKU whose fallback row also fails to resolve is still a refusal. The retry's own reason
replaces the first attempt's — it is the reason that decided this SKU's fate this pass.

### THE READER IS TOLD WHICH SOURCE ANSWERED

`sweep()` returns a fourth value, `resolved_via_fallback`. It names every SKU the retry
rescued, sorted. `cli/cmd_pricearchive.py` prints it as its own line, apart from the
ordinary refusal report. A reader can see the fallback fired. The file does not quietly
change which row priced a SKU with no word said.

### WHAT THIS DOES NOT TOUCH

`cards.number` and `cards.name` are not repaired. The operator's own capture stays exactly
as stored. Other readers — the join, the listing path — depend on it unchanged.
`pipeline/join.py` is untouched. The card row is still tried first, every pass. This only
adds a second attempt after the first one fails. It is never a preference reversal.

### WHAT PROVES IT

`scripts/pricearchive-selftest.py` reproduces both measured shapes. It uses a resolver
built on the real `pricehistory.ProductIndex` and `join.number_index_key`/
`name_index_key`, not a toy stand-in. It proves the fallback resolves both shapes. It
proves a SKU with no fallback, or an unresolvable one, is still a named refusal. It is
mutation-tested: removing the fallback sends both real shapes back to refusing.
