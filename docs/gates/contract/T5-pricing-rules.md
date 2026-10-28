### T5 — Pricing rules

New with batch script v2. Undercut and markup against both bases, rounding half-up at two
decimals, the floor clamp applied *after* rounding, the threshold always read from
`TCG Market Price` whatever the basis, and the `no_market_data` refusal.

- **Pass**: every rule x basis prices exactly; floor clamp applied after rounding;
  threshold always reads market; no_market_data never auto-priced
- "Floor clamp applied after rounding" is also the statement that it cannot be rounded
  under — clamping first would let the rounding step drop the price back below the floor.
- **The floor asserted here is the STORE'S, not the module constant** (D9, amended).
  The case uses a market price between the two figures. Only that shape tells them apart.
  At a stored cut-off of `$0.29`, a `$0.32` card lists at `$0.32`.
  At a cut-off of `$0.40`, the same row clamps to `$0.40` and is not listable. The owner sets the floor.
  `$0.40` is `pipeline/pricing.py`'s module default for a caller with no store, and a store with none set reads `$0.49`.
  It is a regression case, not a parameter sweep. The owner's store sat at `$0.29` for a week while every clamp read `$0.40`.
