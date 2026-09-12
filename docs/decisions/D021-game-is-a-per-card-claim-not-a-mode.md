## D21 — Game is a per-card claim, not a mode

**The game is a per-card claim made on the capture screen, never a mode set on the app shell.** Four capture choices — `pokemon`, `riftbound`, `one_piece`, `pokemon_code` — and the picker sits beside Box, Set hint and Finish.

**`game` joins the claim family and behaves exactly like the others**: client state, resent with every capture, written to the record and the sidecar. **Mixed boxes are therefore legal**, which is not a concession but what makes the claim a claim. A shell-level mode would make the game a property of the *session*, and the first time a Riftbound card turned up in a Pokemon box the operator would have to either lie or stop.

**`game` is required and defaults to `pokemon`, and D3's null-means-no-claim does not transfer.** Worth stating because the two look identical and are not. `FinishClaim`'s `null` is meaningful because there is a **ladder underneath it** that infers a finish from evidence — catalog rows, detection, a human. **There is no ladder that infers a game.** A missing game is not *no claim*; it is *no export*, and every consumer below would have nothing to join against. So the field is required, and the default is a read-side backfill for records written before the field existed — never a write-side default.

**This does not discharge D14.** That entry's mode toggle is the *track* axis — singles versus codes, two schemas, two sales channels, two fulfilment stories sharing one rig. `game` is the *product* axis inside a track. `pokemon_code` sits at the intersection and is why both axes have to exist: a Pokemon product line, captured on the singles rig, disposed of down the codes track (D24).
