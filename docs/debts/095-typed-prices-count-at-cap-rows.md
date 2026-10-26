## DEBT95 — the priced tile counts typed prices on rows the send leaves out

**`typedPrices` counts a stored string answer on an at-cap row, and the send does not.** `Pricing.tsx:typedPrices` tests the answer alone and never reads `at_cap`. `progress.byHand` skips at-cap rows with `continue`. `needsPrice` skips them through the early return in `standing.rowShare`.

- **Result:** the priced tile's "N typed." can count a row the send leaves out. Its figure can differ from the "typed quantities" figure beside it, which skips the same row.
- **Not fixed because** the count is unmeasured on a real store. The size of the gap is not known.
- **Fixed in code:** the tile counts a price on a row that adds copies plus each price change, the rows the send carries. **Delete this entry when** `app/tests/pricing.spec.ts` no longer cites DEBT95 (a builder may not edit it), because the debt ids row of `make docs-audit` fails a citation with no entry.
- **Points to** D277 (Pricing lists all rows; the slim bar's three tiles).

**Outcome at risk.** The priced tile can count a typed price that the press will not send. The tile and the send can disagree.
