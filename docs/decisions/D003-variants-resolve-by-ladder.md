# D3 — Variants resolve by a fixed ladder

**Normal, reverse holo and holo resolve per card down a fixed ladder. Rung 0 does not infer.**

0. **A human's answer, if there is one.** It sits above the ladder, not inside it. `pipeline/join.py` applies it before the walk starts. The routing gate cannot re-queue it. Every rung below infers a finish from evidence. An answer is not an inference. It reads `sku` and `condition` off the live inventory record. So a card the owner ruled on in the review queue keeps that ruling on every later join.

   **It falls through rather than guessing.** If the current export no longer carries that SKU, or carries it under a different Condition, the answer is discarded. The card then walks the ladder as if nobody had answered.

   Gate B exposed the gap. The answer route wrote answers that nothing on the join path read back. Sixteen answered cards re-derived their disagreement on every join and re-parked forever. An answer that does not outlive the question is not an answer. T3 tests it, not T4, because it is a join behavior and not a ladder behavior.

1. **Capture-time metadata.** This is the finish claim from the capture app, stored in the card's JSON sidecar. It is the primary path. `--variant` on the batch script fills the finish where a sidecar records none. It never overrides a recorded finish. The original entry read *only an override*, which would have let a flag replace a recorded toggle.

   Fill gaps, do not override. The toggle is a *claim*. A flag that could flatten a box toggled stack by stack would stop it being one. The flag exists for one case: a directory of photos with no sidecars, where nothing is recorded to override.

   **The claim is a set, not a single finish** (amended by the owner). The claim was one string. One string can describe only a uniform stack. A stack holding two finishes had no honest claim. The operator could name one finish and be wrong about half the cards. Or the operator could claim nothing and discard half of what they knew. Both are worse than saying what is true.

   **The number of members decides what the rung does.** This is the whole of the amendment.

   - **One member behaves exactly as this rung always has.** It determines. It outranks the catalog at rung 2, and detection is cross-checked against it at rung 3. Every card captured before the amendment reads as a one-member claim, and resolves down the identical path.
   - **Two or more members FILTER rather than determine.** The candidate rows are narrowed to the claimed finishes. The rungs below choose within what survives. The catalog decides at rung 2 if exactly one row is left. Detection decides at rung 3 otherwise. The claim is still trusted. It is less specific, and a less specific claim can only narrow.
   - **A filter that empties reviews as `metadata_not_stocked`.** That reason code already means that the operator claimed a finish the number is not stocked in. Claiming `{holo, reverse_holo}` against a number that stocks only `normal` is the same fact as claiming `holo`. The human triage is the same, so no new code is needed.
   - **An empty set is no claim at all.** It matches the null this field has always allowed. It leaves rungs 2 and 3 fully live.

   The shape matches D23's rarity claim: filter the candidates, and contradict if nothing survives. A capture screen whose claims all work one way is one rule to hold.

   **A bare string reads as a one-member set. Nothing writes one.** This is the read-side backfill D21 uses for `game`, with the same boundary. 767 live records, and every sidecar ever written, carry a string. Rewriting them would be a store-wide write that changes nothing a reader cannot do for itself. A new capture always writes a list. So the file converges without a migration and without a version bump.

2. **Catalog-forced.** There is no capture-time metadata, and one condition row exists for that number. Most SV-era rares are holofoil-only. The row decides.

3. **Haiku `finish` field** (`normal | holo | reverse_holo`). It returns in every identification call at no extra cost. It runs as a cross-check even when metadata exists. A normal card mis-sorted into the reverse stack still matches a valid catalog row, so only detection catches it.

4. **Review queue.** The card is still ambiguous. Or detection disagrees with metadata. Or the catalog contradicts metadata. Or no matching catalog row exists.

### The toggle is trusted

The toggle is set per stack, so metadata is a claim, not a hint. Metadata that names a variant the catalog does not stock goes to review. It is not corrected to the only available row. Example: the toggle says normal, and the number has only a holofoil row. This costs a tap per mis-toggled holofoil-only rare. That is the price of the toggle meaning something. It is why rung 2 is reachable only without metadata.

The two review reasons stay distinct, so the queue can be triaged. A run full of contradictions shows that a stack is misfiled. Scattered disagreements across a run show that individual cards are mis-sorted, or that the detector is systematically wrong. Gate B added that third reading, and it is the first one to check. Of 53 normals, 16 read as foil under the rig's lighting. Detection agreed with itself across duplicate copies of the same card. So that run's scattered `metadata_detection_disagreement` rows showed neither a misfiled stack nor mis-sorted cards. The cause was the rig. The numbers are in the gates corpus's `GateB` record. Rung 3 survives this. A cross-check that spends 30% of a run on review taps is still cheaper than one wrong listing.

### Rung 3 may not contradict a claim

The owner ruled that `--bypass` on `banchi join` is retired. The bypass let a run switch off rung 3's contradictions. The reason: at 544 cards, the owner supplied ground truth, and rung 3 was wrong **42%** of the time. 230 cards contradicted a claim that was right every time. The same photograph read differently at two downscales on 19 of 40 cards. The numbers are in the gates corpus's `GateB-note1` record ("Box 2"). A cross-check that is wrong more often than the thing it checks is not a cross-check. A switch that every run flipped was a default wearing a flag. Across 256 bypassed cards, the 16 rulings went to the claim, and box 2's 230 were all wrong.

**The rule now: where a finish claim exists, detection may not contradict it. Detection may still choose inside it.** Suppressing rung 3 wholesale would throw away its real work, which is picking between the members of a multi-finish claim.

**The rule does not reach any other rung.** A card with no claim is decided by rung 3, because no claim exists to resolve it by. A claim the *catalog* contradicts is a different fact from a claim *detection* contradicts. Listing through a catalog contradiction would sell a finish the number is not stocked in. So `metadata_not_stocked` is unchanged. `no_catalog_row` is unchanged, because no row exists to resolve to. The claim decides. It never invents a row.

**A claim-decided card resolves at rung 1.** There is no new stage and no new reason code. Rung 1 means *the claim determined*. The contradictions detection would have raised are set aside before they reach rung 3. `Resolution.bypassed` is retired with the flag. `trust_claim`, `--bypass`, `Resolution.bypassed`, the manifest keys (kept, unread, on old runs) and the reason code are gone. The 16 events stay under a retired label. An entry the old rung queued is released on the next join, since the card now resolves.

### Emit reads the decision back

The bug: `cli/cmd_emit.py` re-derived the decision by calling `resolve.load` a second time, with no claim input. Rung 3 ran live over a run joined under the bypass. It invented a queued position for every bypassed card. It found none of them on disk, because join never wrote them. `emit` then refused with *run `banchi join` first*. Re-running join could not clear it, because join was right. Measured on box 1: `bypassed: 39` in the manifest, 39 positions invented, 39 absent from disk. The refusal's first ten positions matched what the screen printed.

The refusal was the second-worst outcome, and the guard is worth keeping. Had emit's check passed, those 39 cards would have routed to review and left the CSV. The bypass would have been silently void at the step that produces output.

**The fix shape is the rule: a command that re-derives must take every input from the run.** `emit` now needs no flag of its own, and no second place states the decision. T7's `check_emit_claim_decides` covers the current rule. It asserts that the card reaches the import file at the SKU its claim names. It does not assert only that the command stopped refusing.
