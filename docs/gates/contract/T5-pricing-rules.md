### T5 — Pricing rules

New with batch script v2. Undercut and markup against both bases, rounding half-up at two
decimals, the floor clamp applied *after* rounding, the threshold always read from
`TCG Market Price` whatever the basis, and the `no_market_data` refusal.

- **Pass**: every rule x basis prices exactly; floor clamp applied after rounding;
  threshold always reads market; no_market_data never auto-priced
- "Floor clamp applied after rounding" is also the statement that it cannot be rounded
  under — clamping first would let the rounding step drop the price back below the floor.
- **The floor asserted here is the STORE'S, not the module constant** (D9, amended
  2026-09-09), and the case is written on a market price BETWEEN the two figures because that
  is the only shape that can tell them apart: at a stored cut-off of `$0.29` a `$0.32` card
  lists at `$0.32`, and the same row at the `$0.40` default clamps to `$0.40` and is not even
  listable. It is a regression case rather than a parameter sweep — the owner's store sat at
  `$0.29` for a week while every clamp read `$0.40`.
