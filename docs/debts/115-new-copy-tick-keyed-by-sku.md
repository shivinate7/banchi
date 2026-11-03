## DEBT115 — a new copy's tick on the pricing list outlives a change to its price

**What.** On `#/pricing`, the tick on a new copy under Needs You is keyed by SKU alone, so it survives a rule change or a refresh that moves the copy's price. `app/src/Pricing.tsx` keeps `ticks[row.sku]` and clears it only after a send. A live suggestion's tick is keyed to its figure (`tickKey`) and does not have this gap.

- **Result:** the owner ticks a new copy at $26, changes the rule, and the copy goes out at the new figure without a second look. The new figure is on the row, and the send bar counts it.
- **Not fixed because** no server check backs the new-copy tick, the figure stays on screen, and the lane's review cap was reached.
- **Closes when** a new copy's tick is keyed to the figure it approved, as `tickKey` does for live suggestions, with a case in `app/tests/pricing.spec.ts`.
- **Points to** docs/specs/pricing-suggest.md, the Needs you group.

**Outcome at risk.** A card worth $25 or more is listed at a price the owner did not look at.
