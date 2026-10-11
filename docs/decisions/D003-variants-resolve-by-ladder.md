## D3 — Variants resolve by a fixed ladder

**Normal, reverse holo and holo resolve per card down a fixed ladder, under a rung 0 that does not infer.**

0. **A human's answer, if there is one.** It sits above the ladder, not inside it. `pipeline/join.py` applies it before the walk starts. The routing gate cannot re-queue it. Every rung below infers a finish from evidence. An answer is not an inference. It reads `sku` and `condition` off the live inventory record. So a card the owner ruled on in the review queue keeps that ruling on every later join.

   **It falls through rather than guessing.** If the current export no longer carries that SKU, or carries it under a different Condition, the answer is discarded. The card then walks the ladder normally, as if nobody had answered.

   Gate B produced this rung. The answer route wrote answers that nothing on the join path read back. So sixteen answered cards re-derived their disagreement on every join and re-parked forever. An answer that does not outlive the question is not an answer. T3 tests it, not T4, because it is a join behavior and not a ladder behavior.

1. **Capture-time metadata.** This is the finish claim from the capture app, stored in the card's JSON sidecar. It is the primary path. `--variant` on the batch script fills the finish in where a sidecar records none. It never overrides one. (Clarified. This entry once read *only an override*. The implementation would have read that as license to replace a recorded toggle.)

   Fill gaps, do not override. The rest of this entry treats the toggle as a *claim*. A flag that can flatten a box toggled stack by stack would stop it being one. The flag exists for one case: a capture app that does not exist yet, and a directory of photos with no sidecars. There, every card stocked in more than one finish would cost a review-queue tap. Overriding a recorded toggle buys nothing there, because nothing is recorded.

   **The claim is a set, not a single finish** (amended by the owner). The claim was one string. One string can only describe a uniform stack. A stack that holds two finishes had no honest claim. The operator could name one finish and be wrong about half the cards. Or the operator could claim nothing and discard half of what they knew. Both are worse than saying what is true.

   **The number of members decides what the rung does.** This is the whole of the amendment.

   - **One member behaves exactly as this rung always has.** It determines. It outranks the catalog at rung 2, and detection is cross-checked against it at rung 3. The single-claim path does not change. So the amendment is additive, not a rewrite. Every card captured before the amendment reads as a one-member claim. It resolves down the identical path.
   - **Two or more members FILTER rather than determine.** The candidate rows are narrowed to the claimed finishes. The rungs below choose within what survives. The catalog decides at rung 2 if exactly one row is left. Detection decides at rung 3 otherwise. The claim is still trusted. It is simply less specific, and a less specific claim can only narrow.
   - **A filter that empties reviews as `metadata_not_stocked`.** That reason code already means that the operator claimed a finish this number is not stocked in. No new code is needed, because no new situation exists. Claiming `{holo, reverse_holo}` against a number that stocks only `normal` is the same fact as claiming `holo`. The human triage is the same.
   - **An empty set is no claim at all.** It is identical to the null this field has always allowed. It leaves rungs 2 and 3 fully live.

   This is deliberately the shape D23 gave the rarity claim: filter the candidates, and contradict if nothing survives. The two now behave the same way, for the same reason. That is worth more than the feature. A capture screen whose claims all work one way is one rule to hold. The alternative was a finish that determines, beside a rarity that filters. History would be the only explanation for the difference.

   **A bare string reads as a one-member set. Nothing writes one.** This is the read-side backfill D21 uses for `game`, with the same boundary. 767 live records, and every sidecar ever written, carry a string. A migration that rewrote them would be a store-wide write that changes nothing a reader cannot do for itself. The backfill is read-side only. A new capture always writes a list. So the file converges without a migration and without a version bump.

2. **Catalog-forced.** There is no capture-time metadata, and one condition row exists for that number. Most SV-era rares are holofoil-only. The row decides.

3. **Haiku `finish` field** (`normal | holo | reverse_holo`). It returns in every identification call at no extra cost. It runs as a cross-check even when metadata exists. A normal card mis-sorted into the reverse stack still matches a valid catalog row. So only detection catches it.

4. **Review queue.** The card is still ambiguous. Or detection disagrees with metadata. Or the catalog contradicts metadata. Or no matching catalog row exists.

### The toggle is trusted

The toggle is set per stack, so metadata is a claim, not a hint. Metadata that names a variant the catalog does not stock goes to review. It is not corrected to the only available row. Example: the toggle says normal, and the number has only a holofoil row. This costs a tap per mis-toggled holofoil-only rare. That is the price of the toggle meaning something. It is why rung 2 is reachable only without metadata.

The two review reasons stay distinct, so the queue can be triaged. A run full of contradictions means that a stack is misfiled. Disagreements scattered across a run mean individual cards are mis-sorted. Or the detector is systematically wrong. Gate B added that third reading, and it is the first one to check. Of 53 normals, 16 read as foil under the rig's lighting. Detection agreed with itself across duplicate copies of the same card. So that run's scattered `metadata_detection_disagreement` rows meant neither a misfiled stack nor mis-sorted cards. The cause was the rig. The gates corpus's `GateB` record holds the numbers. Rung 3 survives this. A cross-check that spends 30% of a run on review taps is still cheaper than one wrong listing. But the two-way triage above is no longer the whole table.

### Rung 3 can be switched off for a run, and box 2 is why

This is the owner's ruling. The flag is `banchi join --bypass`. The paragraph above kept rung 3 because a 30% false-positive rate is still cheaper than one wrong listing. At 544 cards, the owner supplied ground truth. The rate was **42%.** 230 cards contradicted a claim that was right every single time. The same photograph read differently at two downscales on 19 of 40 cards. The gates corpus's `GateB-note1` record ("Box 2") holds the numbers. A cross-check that is wrong more often than the thing it checks has stopped being a cross-check. 230 review taps against a claim the operator already knows is correct are not a cost the ladder may impose.

**The flag is one rule: where a finish claim exists, detection may not contradict it. But detection may still choose inside it.** Both halves matter. Suppressing rung 3 wholesale would throw away its real work. That work is picking between the members of a multi-finish claim. Suppressing only its power to contradict is the narrowest change that answers the measurement.

**It does not reach any other rung. The same reason makes the flag honest.** A card with no claim is untouched, because nothing exists to resolve it by. `metadata_not_stocked` is untouched. A claim the *catalog* contradicts is a different fact from a claim *detection* contradicts. Listing through it would sell a finish the number is not stocked in. `no_catalog_row` is untouched, because no row exists to resolve to. The operator's own framing sets the boundary. The bypass trusts your claim. It does not invent a row for it.

**A bypassed card resolves at RUNG 1 and is counted.** There is no new stage and no new reason code. Rung 1 has always meant *the claim determined*, and that is what happened. What is new: `Resolution.bypassed` records that a contradiction was set aside. So `join` can report the number, instead of leaving it inferred from a smaller queue. The owner chose that the run report says the card was resolved by the claim. The count is named on the run's stdout, in `report.txt`, and in the manifest as `bypass_detection`, beside its count.

**Per-run and opt-in, never a default.** The precedent is `--review-below-confidence=none`, which this copies on purpose. It is a routing switch the operator sets for a run they can see the shape of. It is not a threshold moved once for everybody. `join --dry-run` shows the shape before the choice. It walks the ladder twice, with the flag and without, and diffs the two queues. It writes nothing.

### The flag is per-run, so every later command has to read it back

**`emit` did not read it back, from the day the flag shipped.** The owner found it while pressing *Write the import files* on a box they had joined. `cli/cmd_emit.py` does not read what `join` decided. It re-derives the decision, calling `resolve.load` a second time. That call passed no `trust_claim`. So it walked the ladder with rung 3 live, over a run joined with the flag. It invented a queued position for every bypassed card. It found none of them in either queue file, because join deliberately never wrote them. It refused with *run `banchi join` first*, at an operator who had. Re-running join could not clear it, because join was right.

**Measured on box 1: `bypassed: 39` in the manifest, 39 positions invented, 39 absent from disk.** The refusal's first ten positions matched what the screen printed, character for character.

**The refusal was the second-worst outcome. That part is worth keeping.** The same resolution writes the import files. Had that check passed, those 39 cards would have been routed to review and left out of the CSV. The bypass would have been silently void at the step that produces output. A guard written for one purpose caught a quieter failure. That is the argument for the guard, not a lucky escape.

**The fix is one line. Its shape is the rule.** `emit` reads `bypass_detection` off the manifest, as it already reads `review_below_confidence`. Both are per-run choices the run recorded. A command that re-derives, rather than reads, must take every input from the run. **There is deliberately no `--bypass` flag on `emit`.** This entry makes the bypass a join-time decision. A second place to state it is a second thing that can disagree with the first. T7's `check_emit_bypass` covers the fix. It asserts that the card reaches the import file at the SKU its claim names. It does not merely assert that the command stopped refusing. A fix that only silenced the refusal would have shipped the quieter failure.

**Amended on the owner's instruction: the cross-check is retired, and the flag's rule is the ladder's.** Every run since Gate B joined with `--bypass`: 256 cards. 16 of 16 rulings went to the claim. Box 2's 230 were all wrong. A switch that every run flips is a default wearing a flag. Detection chooses inside a claim, never against it. `trust_claim`, `--bypass`, `Resolution.bypassed`, the manifest keys (kept, unread, on old runs) and the reason code are gone. The 16 events stay under a retired label. An entry the old rung queued is released on the next join, since the card now resolves. `emit` re-derives the same answer, having no flag to forget (`check_emit_claim_decides`, reduced from `check_emit_bypass`).
