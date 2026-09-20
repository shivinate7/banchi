## D-archive-number-composition — The archive reads the store's own composed number, and the glued-code repair reaches it too

**THE CAUSE, IN ONE SENTENCE.** `pipeline/pricearchive.py:rows_from_store` built its
synthetic export row from the bare `cards.number` alone. It never read the composed
`number_key` column `store/master.py` already writes on every card. So a held Pokemon card
could only be found by name, and the name rung refuses on any ambiguous name.

Separately, `pipeline/pricehistory.py:ProductIndex.find` never tried D55's `strip_set_code`
repair on a miss. The real listing join's own `_walk` already does. A Riftbound read with a
set code glued on the front never got that retry.

### The two mechanisms already existed. Neither was reached from here

This is not a new join. `pipeline/join.py:_key_number_and_printed_total` already composes
this exact key for the real TCGplayer join. `store/master.py:_card_columns` already stores
it on every write as `number_key`, for the FTS5 search index. `pipeline/join.py:_walk`
already tries `_repair_set_code` once, on a miss, before the name rung.

`pipeline/pricearchive.py` and `ProductIndex.find` are a second, independent reader over
the same mirror shape. Both gaps are the same shape of bug: a reader copied one rung of a
ladder (`number_index_key`) without the rungs on either side of it.

### The fix

- `rows_from_store` now selects `number_key` alongside `number`, and `_export_row` prefers
  it. `number_key` is `""` by design for a game with no denominator (Riftbound, One Piece),
  so this changes nothing for them.
- `ProductIndex.find` now tries `join.strip_set_code` once, on a number-index miss, before
  the name rung. Same order, same repair, D55's own shape, reached from a second caller.
- `store/numbers.py:_SET_CODE_PREFIX` widens to also accept a bare space as the separator
  (`SPD 208/221`). The old regex needed one of `•·/-` and missed it. Measured the
  way D67 licensed the original three bounds: zero new matches across all four committed
  exports (2,607 distinct `Number` cells). Read-only against the owner's real store,
  2026-09-20: 41 additional real cases among 3,299 numbered records. None is a real printed
  code — the branch needs an actual space, so `OP15-079` and `SP3/006` are untouched.

### What this does not do

No stored card row is rewritten. `cards.number` stays what capture wrote, per D36. The
archive's reader now composes and repairs at READ time, the way the real join already did.
No mass repair of the `cards` table. The owner's ruling for this task was the mechanism
first, and reassessment after.

### What still refuses, and belongs in the review queue

Read-only against the owner's real store, 2026-09-20, over the last row per SKU
(`rows_from_store`'s own order): of 109 distinct Pokemon SKUs, all in `ME01: Mega
Evolution`, 102 now carry a composed `number_key`. Two do not.

`Exeggutor`'s winning row has a blank number. `Garganacl`'s winning row reads `0934`, a
four-digit misread in a 132-card set. Neither is a shape composition or repair can recover.
Both are the two kinds `CLAUDE.md`'s hard rule names: an absence and a guess. Both belong in
the review queue with their photograph.

Two more of the brief's own examples are the same kind. `Ambushed Recital` has a blank
number. `"Do you have a permit for that?"` has a well-formed `102/166`, but a name that does
not fold to the mirror's own spelling. Its number was never the problem, so this fix does
not touch it.

Among Riftbound cards store-wide, 41 SKUs carry a punctuation-glued set code. D55 already
covered the shape. This reader never reached it until now. 11 more carry the newly widened
space-glued shape, including `Forge of the Flint`'s stored `SPD 208/221` — the exact
refusal named in the sweep.

Whether each repaired key actually finds a row in the tcgcsv mirror is a live-network fact
this worktree cannot check. The repair only tries the stripped key. It never invents a
match. A card whose stripped key still misses stays exactly as refused as before.

Governs: `pipeline/pricearchive.py`, `pipeline/pricehistory.py:ProductIndex`,
`store/numbers.py:_SET_CODE_PREFIX`. Proved by `harness/tests/t7_store_and_seams.py` (the
glued-code repair, mutation-tested by removing it) and `scripts/pricearchive-selftest.py`
(the number-key composition, mutation-tested the same way).
