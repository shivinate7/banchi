## 42 — ~~A row with no market price hides a typed price that the send still lists~~ — CLOSED 2026-09-26, on the owner's word

**Closed on the owner's ruling, "Screen shows $5.16"** (`docs/reviews/ux-2026-09-23/RULINGS.md`).
The screen side was fixed and the send was not changed. `app/src/standing.ts:corpusAnswer` and
`Pricing.tsx`'s `answerFor` read a `price` answer on every row, the same as `join` reads it. The
row shows the typed price and a quiet "No market price" mark. Home counts the copy as ready. One
case in `app/tests/pricing.spec.ts` and one in `app/tests/home.spec.ts` were red on the old code.


**The gap.** A SKU can hold a typed price on the `price` channel and then lose its market
price in a later export. `#/pricing` reads a row with no market price from the `unknown`
channel only. So the row shows an empty field and "Needs a price". The send does not agree.
`pipeline/corpus.py:Corpus._decisions` puts every `price` answer in `overrides`, and
`pipeline/join.py:prices_for` reads `overrides` before it asks whether the row has a market
price. So the card lists at the old typed price.

**Found by the final Pricing review of the undo round, 2026-09-26.** Void Assault had a typed
$5.16, and its market went blank in a scratch export. The screen said "Needs a price". Checked
in code on 2026-09-26: `Corpus._decisions` on that answer gives a `flat_price` disposition of
$5.16 and no `no_market_data` entry. The send itself was not run.

**What it costs.** The screen and the send disagree about one row. The owner sees a row that
owes a price, but a send lists it at a price the screen does not show. The send is not
refused, and no copy is lost.

**Why it is not fixed.** It is older than the undo round and outside its scope. A fix must
choose which side is right: the screen reads the `price` answer on a no-market row, or join
stops using it. That choice is the owner's.

**The fix, not built.** Pick one reader rule for a no-market row and use it in
`app/src/standing.ts:corpusAnswer`, `Pricing.tsx`'s `answerFor` and join. A hold already
follows join's rule on every row (the undo round's hold fix).

Cites D277 (Pricing is one list and one send).
