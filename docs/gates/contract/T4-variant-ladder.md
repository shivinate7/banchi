### T4 — Variant ladder

For a card with normal, holo, and reverse rows in the fixture, assert each ladder stage
resolves to the correct condition string and price: metadata-driven, catalog-forced,
detection-driven, and the claim-decides path.

Also the routing table (batch script v2 §5.4) — which queue a card lands in, since that is
the other thing that decides whether a resolved card is listed:

- confidence `low` + market ≥ $0.40 → **main** review queue, not listed
- confidence `low` + market < $0.40 → **parked**, not listed, not dropped
- ladder → review: main if the cheapest candidate row is ≥ $0.40, parked if below
- no catalog row, or identification failed → main, sorted last
- matched row with blank or $0.00 market → `no_market_data`, never auto-priced and never
  swept into the sub-threshold flat price
- `--review-below-confidence=none` restores "confidence never routes on its own"

- **Pass**: all four stages correct, a finish claim is never contradicted by the photograph,
  and every routing row sends the card to the queue named

**The ladder's vocabulary became PER GAME on 2026-08-23, and this test caught nothing about
it because nothing had asked.** `variant.resolve` checked every game's finish against
`variant.FINISHES` — Pokémon's three — and did not refuse politely: it RAISED
`UnknownFinish`, so a Riftbound card claiming `foil`, a finish that game's own registry
entry authors and the capture screen offers, would have taken a join down with a stack
trace. Covered now in both directions, because the fix must not have widened Pokémon's enum
to make the crash go away: `foil` resolves under `riftbound` and still raises under
`pokemon`.

The same class of defect sat one seam further on. `cli/resolve.py` whitelisted the model's
detected finish against the same Pokémon enum, so `foil` landed as `None` and D3 rung 3's
cross-check was lost for every non-Pokémon card — a silent drop, forbidden in as many words
by the comment attached to the line committing it. **The enum-widening case moved with the
home it guards**: it used to assign to `variant.FINISHES`, and now widens the registry
entry, so it exercises `cli/resolve.py` → `variant.vocabulary` → `pipeline/games.py`. T7
keeps the source half and asserts the defective expression is gone rather than the token,
so the comment may still explain what went wrong.

**D3's set-valued rung 1 is covered at every exit** (amended the same day). One member
resolves identically to the bare string it replaces — the compatibility guarantee — and two
or more narrow the rows and fall through: to rung 2 when the claim leaves one row, to rung 3
when detection picks inside the claimed set, to `metadata_detection_disagreement` when it
picks outside, to rung 4 when two rows survive with no detection, and to
`metadata_not_stocked` when no member is stocked at all. Ordering and dedup are asserted,
and one bad member refuses the whole claim rather than being dropped from it.

**Three mutations were observed failing before those cases were kept**: rung 1 returning
instead of falling through, `vocabulary` ignoring its game argument, and `_check_claim`
dropping unknown members. A case that cannot fail is not coverage.
