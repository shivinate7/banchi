## DEBT-tile-presses-guard-unproven — the Show Held and Price Them clears have never gone red

**The guards for the "Show Held" and "Price Them" presses have never gone red.** Each press clears the other filters through `Pricing.tsx:showRows`. The guards are `pricing.spec.ts` tests `send tiles: Show Held after a search and a game facet clears both, and shows every held row` and `send tiles: Price Them after a search and a game facet clears both, and shows every unpriced row`.

- **Result:** the two tests pass on the current code. Nothing shows that they fail when a press keeps a filter on or clears the wrong one.
- **Not fixed because** the red case needs a product change. A broken clear cannot be shown to fail on the current code.
- **Closes when** each test goes red on a broken clear, then green on the fix. A guard that has never gone red is not trusted.
- **Points to** D277 (Pricing lists all rows; the slim bar's three tiles).

**Outcome at risk.** A press could show the wrong rows, and both tests would still pass.
