## 24 — A zero reading cannot tell a sold-out listing from an import sitting in Staged

**The defect this section was opened for is FIXED**, by `D150`, the day
after it was written. What is left is one ambiguity underneath it, and it is worth a section
of its own rather than a line in that entry because it is the third defect to turn on the same
missing field.

### What was fixed, so this is not read as still open

`cli/resolve.py:_copies_out` ages a stuck `pushed` claim by the SKU's sales only where the
export corroborates them. It now reads the export's reading for two answers instead of one: a
reading that reports copies LIVE vouches for every sale of the SKU, and **a reading of NOTHING
vouches for exactly the sales it was taken AFTER** — a zero read four days after a copy sold is
that sale's own result, not evidence the copy was never listed. The seven stranded SKUs this
section tabulated are all offered now, Falling Star and Fizz, Trickster among them, and run
`2026-09-11-box1-01` went from 239 of 246 SKUs and 310 copies to **246 and 317**. The report
sentence this section also held — `nothing_to_add`'s *"every copy in this run is already listed
or has left the box"*, false about a card sitting in the box — went with them: it was false
because the arithmetic was.

### The residue

**A SKU whose import landed in TCGplayer's Staged channel and never went live reads `Total
Quantity` 0 as well.** A copy marked sold by hand against that state now ages a claim it should
not, and the staged rows are still out there — so the next emit offers a copy of a row
TCGplayer may already be holding.

It is strictly narrower than what the gate refused before, which refused every sale under a
zero reading, and the direction of the trade was the operator's: 58 copies of real backstock across 32 SKUs
stranded against an unmeasured number of staged rows on a store whose operator does not stage
by hand. **Nothing has ever measured how often the residual case occurs**, and that is the
honest statement of it — `staged` is written only by `reconcile`, which this operator does not
run, so the store cannot tell the two apart even in hindsight.

### What closes it

**A marker that a copy actually reached an import file** — D59's own named reopener, one field
on `Card` written by `cmd_emit`'s push loop beside the `sku` stamp. With it the committed set is
READ rather than inferred, and a sale of a copy carrying the marker ages the claim on the
copy's own evidence rather than on a reading's silence. **This is the third entry to turn on
not having it**, after D147 and the defect above, which is the argument for building it.

**Or a reconcile.** `pkmnscan reconcile --live` writes `live` and `staged`, and both halves of
the ambiguity become facts. The operator does not run it, which is why this is a debt.

**The number may move, and nothing allocates it.** 24 is what was next on 2026-09-11 —
renumber it rather than another branch's, the way this file's header already rules.
