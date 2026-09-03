# Settled decisions — singles pipeline

Every entry here is closed. Sessions do not re-litigate them. To reopen one, name the entry and the new evidence, then wait for the owner. Rewrite entries in place when a decision changes — do not append history.

---

## D1 — Two-phase architecture

**Capture is fast, offline and dumb; identification and pricing happen later, in batch.**

Capture is fast, offline, and dumb. Identification and pricing happen later in batch. Never merge them: speed, cost, and reliability all favor the split.

## D2 — Identification is Claude Haiku vision, owned end to end

**Identification is Claude Haiku vision over the Batch API, owned end to end.** OCR was researched and rejected at ~85–90% accuracy. Perceptual hashing is deferred to v2 as a cross-check. Haiku costs ~$5–15 per 10k cards via the Batch API, which is negligible. The set hint is an optional accelerator recorded in the capture app: identification works without it, better with it.

**TCGplayer Scan & Identify was evaluated and rejected as a pipeline component.** It is UI-only with no API contract, inserts a manual browser step into an autonomous flow, does not guarantee per-image to position mapping, and couples identification to one platform. No integration code is written, ever.

**It is also not a precondition for anything** (changed 2026-08-03). It was previously the required next step whenever T1 scored below the floor, which put a manual browser session on the critical path between a red harness and any attempt to fix it — the tail wagging the dog. A sub-floor T1 is now worked directly. Scan & Identify is parked in the Someday list as an optional reference point: it answers *is this task hard, or is our prompt weak?*, which is worth knowing eventually and worth nothing urgently.

Evaluate any future third-party integration on: API or UI? Does it return the data the core depends on? Does the cost it replaces matter? Does it add a manual step? Does it couple us to one platform?

## D3 — Variant resolution ladder

**Normal, reverse holo and holo resolve per card down a fixed ladder, under a rung 0 that does not infer.**

0. **A human's answer, if there is one** (added 2026-08-22). Above the ladder rather than a rung inside it: `pipeline/join.py` applies it before the walk below starts, and the routing gate cannot re-queue it. The distinction is the point — every rung below infers a finish from evidence, and an answer is not an inference. It reads `sku` and `condition` off the live inventory record, so a card the owner has ruled on in the review queue keeps that ruling on every later join.

   **It falls through rather than guessing.** If the current export no longer carries that SKU, or carries it under a different Condition, the answer is discarded and the card walks the ladder normally — the same as if nobody had answered.

   Recorded here because Gate B is what produced it: the answer route wrote answers that nothing on the join path ever read back, so sixteen answered cards re-derived their disagreement on every join and re-parked forever. An answer that does not outlive the question is not an answer. Tested by T3, not T4 — it is a join behavior, not a ladder behavior, which is the same distinction this entry draws.
1. **Capture-time metadata** — the finish claim in the capture app, stored in the card's JSON sidecar. Primary path. `--variant` on the batch script **fills the finish in where a sidecar records none, and never overrides one** (clarified 2026-08-03; this entry previously read *only an override*, which the implementation would have had to read as license to replace a recorded toggle).

   Fill-gaps rather than override, because the rest of this entry spends three paragraphs establishing that the toggle is a *claim* — and a flag that can flatten a box you toggled stack by stack is precisely what makes it stop being one. The case the flag exists for is the capture app not existing yet: a directory of photos with no sidecars at all, where every card stocked in more than one finish would otherwise cost a review-queue tap. Overriding a recorded toggle buys nothing there, since there is nothing recorded to override.

   **The claim is a set, not a single finish** (amended 2026-08-23, by the owner). It was one string, and one string can only describe a stack that is uniform. A stack that genuinely holds two finishes had no honest claim available: the operator could name one finish and be wrong about half the cards, or claim nothing and throw away the half of the truth they did know. Both are worse than saying what is actually true.

   **How many members it has decides what it does, and this is the whole of the amendment:**

   - **One member behaves exactly as this rung always has.** It determines. It outranks the catalog at rung 2 and it is what detection is cross-checked against at rung 3. Nothing about the single-claim path changes, which is what makes this amendment additive rather than a rewrite — every card captured before that day reads as a one-member claim and resolves down the identical path.
   - **Two or more members FILTER rather than determine.** The candidate rows are narrowed to the claimed finishes, and the rungs below choose within what survives — the catalog at rung 2 if exactly one row is left, detection at rung 3 otherwise. The claim is still trusted; it is simply less specific, and a less specific claim can only ever narrow.
   - **A filter that empties reviews as `metadata_not_stocked`**, the reason code that already means the operator claimed a finish this number is not stocked in. No new reason code, because no new situation: claiming `{holo, reverse_holo}` against a number that stocks only `normal` is the same fact as claiming `holo` against it, and the triage a human does is the same.
   - **An empty set is no claim at all**, identical to the null this field has always allowed, and it is what leaves rungs 2 and 3 fully live.

   **This is deliberately the shape D23 gave the rarity claim** — filter the candidates, contradict if nothing survives — and the two now behave the same way for the same reason. That is worth more than the feature: a capture screen whose claims all work one way is one rule to hold, and the alternative was a finish that determines beside a rarity that filters, with nothing but history to explain the difference.

   **A bare string reads as a one-member set, and nothing ever writes one.** The same read-side backfill D21 uses for `game`, chosen for the same reason and with the same boundary: 767 live records and every sidecar ever written carry a string, and a migration that rewrote them would be a write across the whole store to change nothing any reader could not do for itself. Read-side, never write-side — a new capture always writes a list, so the file converges without a migration and without a version bump.
2. **Catalog-forced** — no capture-time metadata, and one condition row for that number (most SV-era rares are holofoil-only), so the row decides.
3. **Haiku `finish` field** (`normal | holo | reverse_holo`), returned in every identification call at no extra cost. Runs as a cross-check even when metadata exists: a normal card mis-sorted into the reverse stack still matches a valid catalog row, so only detection catches it.
4. **Review queue** — still ambiguous, detection disagrees with metadata, the catalog contradicts metadata, or no matching catalog row.

### The toggle is trusted

It is set per stack, so metadata is a claim and not a hint. Metadata naming a variant the catalog does not stock — toggle says normal, the number has only a holofoil row — reviews rather than being corrected to the only available row. This costs a tap per mis-toggled holofoil-only rare; that is the price of the toggle meaning something, and it is why rung 2 is reachable only without metadata.

The two review reasons stay distinct so the queue can be triaged: a run full of contradictions means a stack is misfiled, while disagreements scattered across a run mean individual cards are mis-sorted — or that the detector is systematically wrong, which is the reading Gate B added on 2026-08-22 and the first one to check now. 16 of 53 normals read as foil under the rig's lighting, and detection agreed with itself across duplicate copies of the same card, so that run's scattered `metadata_detection_disagreement` meant neither a misfiled stack nor mis-sorted cards: it meant the rig. `docs/GATES.md`'s Gate B section holds the numbers. Rung 3 survives it — a cross-check that spends 30% of a run on review taps is still cheaper than one wrong listing — but the two-way triage above is no longer the whole table.

### Rung 3 can be switched off for a run, and box 2 is why

The owner's ruling, 2026-08-24; `pkmnscan join --bypass`. The paragraph above kept rung 3 on the argument that a 30% false-positive rate is still cheaper than one wrong listing. At 544 cards with the owner supplying ground truth, the rate was **42% — 230 cards contradicting a claim that was right every single time** — and the same photograph read differently at two downscales on 19 of 40 cards. `docs/GATES.md`'s box-2 section holds the numbers. A cross-check that is wrong more often than the thing it checks has stopped being a cross-check, and 230 review taps against a claim the operator already knows is correct is not a cost the ladder is entitled to impose.

**The flag is one rule: where a finish claim exists, detection may not contradict it — but it may still choose inside it.** Both halves matter. Suppressing rung 3 wholesale would throw away its real work, which is picking between the members of a multi-finish claim; suppressing only its power to contradict is the narrowest change that answers the measurement.

**It does not reach any other rung, and the reason is the same one that makes the flag honest.** A card with no claim is untouched, because there is nothing to resolve it by. `metadata_not_stocked` is untouched, because a claim the *catalog* contradicts is a different fact from a claim *detection* contradicts, and listing through it would sell a finish the number is not stocked in. `no_catalog_row` is untouched, because there is no row to resolve to. The operator's own framing is the boundary: the bypass trusts your claim, it does not invent a row for it.

**A bypassed card resolves at RUNG 1 and is counted.** No new stage and no new reason code: rung 1 has always meant *the claim determined*, which is exactly what happened. What is new is that `Resolution.bypassed` records that a contradiction was set aside, so `join` can report the number rather than leave it inferred from a smaller queue — the owner's choice was *resolved by the claim, and the run report says so*. It is named on the run's stdout, in `report.txt`, and in the manifest as `bypass_detection` beside its count.

**Per-run and opt-in, never a default.** The precedent is `--review-below-confidence=none`, which this deliberately copies: a routing switch the operator sets for a run they can see the shape of, rather than a threshold moved once for everybody. `join --dry-run` exists so the shape is visible before the choice — it walks the ladder twice, with the flag and without, and diffs the two queues, writing nothing at all.

### The flag is per-run, so every later command has to read it back

**And `emit` did not, from the day the flag shipped** — found by the owner 2026-08-30, pressing *Write the import files* on a box they had joined. `cli/cmd_emit.py` does not read what `join` decided; it re-derives it, calling `resolve.load` a second time. That call passed no `trust_claim`, so it walked the ladder with rung 3 LIVE over a run joined with the flag — inventing a queued position for every bypassed card, finding none of them in either queue file because join deliberately never wrote them, and refusing with *run `pkmnscan join` first* at an operator who had. Re-running join could not clear it, because join was right.

**Measured on box 1: `bypassed: 39` in the manifest, 39 positions invented, 39 absent from disk.** The refusal's first ten positions matched what the screen printed character for character.

**The refusal was the second-worst outcome, and that is the part worth keeping.** The same resolution is what writes the import files, so had that check passed, those 39 cards would have been routed to review and left out of the CSV — the bypass silently void at the one step that produces output. A guard written for one purpose caught a different and quieter failure, which is the argument for the guard rather than a lucky escape.

**The fix is one line and its shape is the rule: `emit` reads `bypass_detection` off the manifest exactly as it already reads `review_below_confidence`.** Both are per-run choices the run recorded, and a command that RE-DERIVES rather than reads must take every input to that derivation from the run. **There is deliberately no `--bypass` flag on `emit`**: this entry makes the bypass a join-time decision, and a second place to state it is a second thing that can disagree with the first. Covered by T7's `check_emit_bypass`, which asserts the card reaches the import file at the SKU its claim names — not merely that the command stopped refusing, because a fix that only silenced the refusal would have shipped the quieter failure.

**Amended 2026-09-02 on the owner's instruction: the cross-check is retired, and the flag's rule is the ladder's.** Every run since Gate B joined with `--bypass` (256 cards), 16 of 16 rulings went to the claim, box 2's 230 were all wrong: a switch every run flips is a default wearing a flag. Detection chooses inside a claim, never against it. `trust_claim`, `--bypass`, `Resolution.bypassed`, the manifest keys (kept, unread, on old runs) and the reason code are gone; the 16 events stay under a retired label; an entry the old rung queued is released on the next join, since the card resolves; `emit` re-derives the same answer, having no flag to forget (`check_emit_claim_decides`, reduced from `check_emit_bypass`).

## D4 — Review queue is digital-only

**The review queue is digital, and the physical card never leaves its box.**

Shows the stored capture photo beside candidate catalog rows for a one-tap choice. The physical card never leaves its box; unresolved cards stay unlisted at a known position.

## D5 — Two personas

**Two personas share one store: the owner processes, a family member fulfills.**

The owner handles capture, processing, pricing, imports, and settings. A retired, non-technical family member handles fulfillment from his own device. Fulfillment-facing screens must be self-evident. Constraints in `docs/DESIGN.md`.

## D6 — Photo service and pull preview

**One photo route serves the review queue and the pull preview alike.**

The capture server serves stored photos at `GET /photo/<box>/<position>`. The review queue requires it; the pull modal reuses it, showing the card's own capture photo beside its location before pulling. Photos are position-keyed on disk — this is display, not new storage.

## D7 — Duplicates aggregate by SKU at join time

**Multiple copies of one card and variant collapse into ONE fixture row with `Add to Quantity` = copy count.** Inventory keeps every copy as its own position with its own photo; the app maps SKU to all positions holding it.

**Live quantity caps at 4 per SKU** (a playset; configurable) regardless of copies owned. This blocks envelope-buster orders, and a price spike sells at most 4 stale-priced copies before repricing — the same rationale behind TCGplayer's own Buylist Max Listing feature.

Excess copies are backstock at known positions. Refill on later imports as `Add to Quantity = min(cap - live, backstock)`, with live quantities read from Export From Live. Price is per-SKU and shared across copies.

### Copies are fungible, and `live` is a quantity rather than a set of addresses

Amended 2026-08-23 by the owner. This entry used to say order pulls *select specific positions*, and `cli/cmd_join.py` implemented that literally: it walked `positions_for_sku`, filtered to staged copies, and promoted the first N of them, so four of seven identical cards were sellable and three were not for no physical reason at all. The owner's words: if I have 15 of one copy and mark 3 as live, it's any 3 are live, not 3 specific locations.

So the three listing stages moved off the card and onto the SKU:

- A position's `state` is `captured`, `identified` or `sold`, and describes one physical card. `pushed`, `staged` and `live` are no longer members of `master.STATES`, and `check_state` refuses them — which is what stops a caller reaching for the old `set_state(key, LIVE)` and quietly getting a per-position flag back.
- `store/master.py:Listing` holds `pushed` / `staged` / `live` as counts per SKU.
- **Every unsold copy is sellable.** The pull marks whichever copy the hand reached, and the sale decrements the SKU's `live` count, floored at zero.
- Copies on hand is a count of unsold positions; listed quantity is `min(cap, on hand)`.

**That last `min` reached the pipeline and not the screen, until the owner caught it on 2026-08-25.** `pipeline/join.py:add_to_quantity` has always bounded by the copies actually held (`min(room, uncommitted)`), but `GET /search` sent the bare `LIVE_QUANTITY_CAP` and `CardLocations.tsx` drew it as the denominator of `listed N of ...` — so a card the owner had exactly one of read **`listed 0 of 4`**, two inches from `on hand 1`. Not wrong about the cap; wrong about what a fraction means. A denominator is read as what is achievable, and three of those four copies do not exist — which is the failure D20 spends its whole entry on, at SKU scale instead of box scale.

`SearchGroup` now carries **both**: `cap` is the rule, `listable` is `min(cap, on hand)` for that SKU. Computed server-side, because `app/src/server.ts` records that the app is forbidden from computing the live cap and a `Math.min` in TypeScript is that rule kept in two places. T7 asserts the arithmetic rather than the literal, so it moves the day the cap does.

**The decrement is an optimistic local estimate, and that is not a weakness of it.** D8 and D11 already put the authority in the TCGplayer export's `Total Quantity`, which `join` reads on every run — so this number was never a second source of truth competing with the export, and a run corrects whatever drift a between-run sale introduced. The failure this ordering prevents is the opposite one: holding the count back until a join makes the app disagree with the shelf the operator is standing in front of.

**Backstock is therefore a number, not a place.** *Excess copies are backstock at known positions* above stays true in the only sense that matters — every copy is at a known position and the app maps SKU to all of them — but no copy is *designated* backstock, and nothing may reintroduce a per-position listing flag to make it so.

### And that map was false for every copy past the fourth

Found by the owner 2026-08-30. `cli/cmd_emit.py` wrote the card's identity — `sku`, `condition`, `run` — inside a loop over `SkuMatch.live_positions`, which is `uncommitted_positions[:add_to_quantity]` and therefore bounded by the `live_cap` of 4. So the cap reached the one thing this entry says it has nothing to do with: **how many copies of a card we know the name of.**

**The owner's own words on finding it are the whole argument**: this was supposed to be a gentle heads up to list four as a default, mainly for cheap cards, and it was not supposed to take the shape it had taken. The cap is a rule about the LISTING — the envelope-buster order and the stale-price spike named two paragraphs up — and it had quietly become a rule about the RECORD.

**An unstamped copy is not backstock in the sense defined above.** Backstock is a number, and `backstock_positions` is a real answer this pipeline already computes; a copy with `sku: null` is something else entirely — invisible to `GET /search`, absent from `positions_for_sku`, and uncounted by `copies_on_hand`. The map this entry promises simply did not contain it.

**Measured on the owner's store the day it was found: Rengar, Trophy Hunter (9189797, $30.81) holds SEVEN copies — 3/1, 3/2, 3/4, 3/17, 3/20, 3/30, 3/36 — and four carried the SKU.** The screen reported four on hand for a card there are seven of, and the three it could not see were the most valuable cards in the box.

**The stamp runs over `uncommitted_positions` and the count still runs over `live_positions`, and keeping those two apart is the fix rather than a detail of it.** `pushed` is a commitment that a CSV row was written; a backstock copy has no row. One increment serving both loops would push the count past `add_to_quantity` and double-stage on the next import, which is the failure `docs/GATES.md` records from the first real post-import re-emit.

**It is `uncommitted_positions` and deliberately not `positions`, which is the one way this fix could have been worse than the defect.** The obvious repair is to iterate every matched position, and it destroys data. `cli/resolve.py` marks a copy committed on either of two grounds — a count read back off the `Listing`, or **the copy being in a TERMINAL state** — so every sold and retired copy of a matched SKU sits in `match.positions`, and `store/master.py:set_state` has no terminal guard. Iterating them would move a sold card to `identified`, taking D10's permanent gap and D26's terminal state with it, silently. Measured on the same run: **eight of its 33 matched positions are sold today**, so one re-emit would have resurrected all eight. `uncommitted_positions` cannot contain a departed copy by construction.

**Nothing is given up by excluding the committed ones.** A copy committed by COUNT was chosen by `_committed_keys` out of `copies_on_hand`, which selects on `sku` — so it is already stamped. A copy committed by having LEFT is not this command's to relabel.

**Idempotence is untouched, and this is worth stating because it is the first thing to doubt.** It lives in `cli/resolve.py:_committed_keys`, which reads the `Listing` counts and never `card.sku`, so widening what gets stamped cannot move what gets pushed. D54's rule that a re-emit adds and never subtracts is unaffected.

**What it recovers is small today and structural from here.** Three cards on the owner's store — Rengar's backstock — because only two runs have ever been emitted and only one SKU in them holds more copies than the cap. The 502 of 715 records carrying `sku: null` are overwhelmingly not this: **498 of them are box 2, whose run was joined and never emitted at all**, and that is a different gap with a different remedy.

**A second effect, named smaller than it was first claimed because the measurement did not support the larger claim.** `_committed_keys` slices `copies_on_hand(sku)[:held]`, and an unstamped copy is missing from that list — so the slice could return fewer keys than `held` and under-count `committed_positions`, inflating `add_to_quantity`. Full stamping makes that list complete and the shortfall structurally impossible where the copies exist. It fixes **nothing on the store today**: four SKUs there are currently short, and all four are short because their stamped copies SOLD — and a sold copy is committed by the terminal branch instead, so the count comes out right anyway. Recorded as a hole closed rather than a bug fixed.

**Covered by T7's `check_emit_identity_stamp`, in its own isolated home.** Seven copies of a holofoil-only number: every copy carries the SKU, `pushed` stops at the cap, the import file asks for exactly the cap on one row, and a sold copy survives a re-emit. Three mutations were observed failing before it was kept — the original `live_positions` loop, the naive `match.positions` loop, and a shared increment — each red on a different assertion.

### The cap itself is the owner's next question, recorded rather than built

On being shown the fix above and the note that a value-dependent cap was the other half of their instruction, 2026-08-30: they would like to make the cap value-related, but for now what was done is fine. So the flat 4 stands, and this paragraph is the marker that it stands by default rather than by argument.

**What is being questioned is the FLATNESS, not the cap.** The reasoning above it is untouched — a cap still blocks the envelope-buster order, and it still bounds how many copies a price spike can sell at a stale number. What the owner's framing calls into doubt is one number serving every card. The measurement that makes it concrete is on their store, and it is the same card this amendment is about — Rengar at **$30.81**, capped at four by a default reasoned about with commons in mind. D9 already draws exactly this line one register over, where the threshold and the floor are both derived from a labor bar rather than picked; a cap derived the same way would be a number with an argument behind it instead of a constant nobody has revisited.

**It is a change to THIS ENTRY when it is made, and the shape is already sitting here.** `SkuMatch.live_cap` is a per-match field with `LIVE_QUANTITY_CAP` as its default, and `pipeline/join.py:build` takes `live_cap` as an argument — so a rule that reads the row's own market price has somewhere to live without a schema change and without a new field on the wire. What it would need is the argument: which bands, what the cap is in each, and whether it is a per-run choice like D9's sub-threshold disposition or a standing rule. None of that has been argued, and **a cap that varies is a cap an operator has to be able to predict**, so the screen half is part of the question rather than a follow-up to it.

**Nothing is blocked on it and nothing should wait for it.** The defect above is that the cap reached the RECORD, and that is fixed whatever the cap turns out to be — the identity write no longer reads `live_cap` at all, so this decision can be taken later without touching that seam again.

## D8 — Pricing source is the TCGplayer Filtered CSV export itself

**Pricing comes from the TCGplayer Filtered CSV export and from no external API.**

It carries live, per-SKU, per-variant `TCG Market Price`. Threshold checks and pricing rules run directly against it. No external pricing API.

pokemontcg.io data serves identification support (set IDs, collector numbers, printedTotal) and eval images only — never pricing. That role is unchanged by D15, which vendors the same data locally: the split above is why a snapshot is safe, since nothing price-shaped is in it. Read this entry as naming what the data is *for*, not as authorizing a call to the live API.

## D9 — Threshold and floor are both $0.40

**Threshold and floor are both $0.40, and both are derived from the $60/hr labor bar** rather than picked: a marginal pull is ~20s, and 0.8675 x $0.40 clears it. Both configurable.

- **Threshold**: market >= $0.40 earns a listing.
- **Floor**: listed price = `max(pricing-rule output, $0.40)`, clamping undercut rules in collapsing markets. TCGplayer's own seller guidance is to set the floor where a sale loses money including labor, and always price above it.

Pricing rules: match / undercut % / markup %.

**Sub-threshold disposition is a per-run choice, never a constant in the code.** The owner picks one default for the run — flat at the floor, or a flat price set for that run — and can name individual SKUs to override it. Output is suppressed until that choice is made: a card under the threshold is not quietly listed and not quietly dropped.

**A row with a blank or $0.00 market price is `no_market_data`, and is not sub-threshold.** A missing price is an unknown price, not a low one, so it gets no disposition at all — not the flat price, not the floor, not the bulk lot. It is priced by hand in `decisions.json` or explicitly left unlisted, and `emit` refuses to write while one is unanswered. Recorded because the tempting fix is to sweep these into the sub-threshold bucket, whose whole point is describing cards whose value is *known* to be small. The failure that prevents: handing away a $40 chase card at the $0.40 floor because its market cell happened to be empty.

The join preserves the sub-threshold price distribution in bands rather than lumping it, because *everything under $0.40* hides the difference between a $0.38 rare and a $0.01 code card, and that difference decides later which of them are worth a bulk lot. Bands are cut as fractions of the threshold, so they follow it if it moves.

TCGplayer's native Bulk Lots category (Level 4, Pricing tab) remains the exit for whatever is not listed — selected against that distribution, not sorted into blindly at emit time. No eBay needed.

**Amended 2026-09-02, on the owner's decision: the sub-threshold disposition is a standing STORE policy with a default, and output is no longer suppressed for want of it.** The answer is `inventory/prices.json`'s `policy.sub_threshold` (D86) — one for the whole store, not one per run — and the default is **flat $0.49**: `pipeline/corpus.py:DEFAULT_SUB_THRESHOLD`, applied by `Corpus.parse` wherever the key is absent or null and written to the file on the next ordinary save, never on read. A file that says `"floor"` or a flat price says what it says; only silence takes the default. *"Per-run choice, never a constant in the code"* above is retired: the constant is the owner's own answer, given once, and the per-lot exception survives as `Corpus.overrides` for the run that genuinely wants its own. The `no_market_data` paragraph below is unchanged — a missing price is still an unknown price, still answered by hand, and `emit` still refuses while one is unanswered.

## D10 — Inventory model

**A card gets a sequential position at capture, and positions are never renumbered.** Location is Box N, Section N, Card N. Sold cards leave permanent gaps.

### Sections are per-box and declared at capture time

Amended 2026-08-23 by the owner. `CARDS_PER_SECTION = 25` was a bare module literal no env var, flag or parameter could reach, and real boxes have dividers where the operator physically put them. A box now carries its own list of divider indices — `[1, 31, 56]` means section 2 starts at card 31 — set at the moment the real divider goes in.

**An empty list means undeclared, an undeclared box is one section, and there is no automatic divider** (amended 2026-08-29, the owner: delete automatic sectioning). This paragraph read that an empty list means undeclared and the 25-rule renders it, defended as keeping every label written before boxes existed byte-identical. That was true and it was the wrong trade. The 25-rule cut a divider into every undeclared box every twenty-five cards whether or not one was in the plastic, and byte-identical labels are worth nothing when what they are identical to is a boundary nobody put there.

**The measurement is the owner's own store.** Box 1 holds 133 cards and declares no layout, so it rendered as six sections and a person sent to `Section 4 · Card 8` would have been counting for a divider that does not exist. Box 2 declares `[1, 86, 171, 253, 394]` and is untouched, as is every other declared box: the change reaches exactly the boxes that never claimed to have dividers.

**What replaces the constant is `(1,)` — the one divider every box really has, at its front.** `pipeline/join.py:Position.layout` states the fallback once and `section`, `section_start` and `section_end` all read it, where the constant had three branches doing their own arithmetic. So `card` is the index, `section` is 1, and `section_end` is None, which is D20's existing answer for a final section rather than a new rule — the caller holding the box's capacity fills it in. `Position` is still the only label formula in the repo, and the v1 to v2 migration still writes an empty layout for every box it finds; only what an empty layout RENDERS AS has moved.

**The labels of every undeclared box moved once, deliberately, and that is the cost.** It is the same risk `harness/tests/t7_store_and_seams.py` names for the migration — every position label in a real inventory shifting at once, with the only symptom a person opening the wrong slot weeks later — realized on purpose instead of by accident. It is affordable because a label was never printed on anything, only ever read live off a screen. T7 pins the new strings so that the next such shift is not accidental either.

### The `New section` control is `S` on the capture screen

Built 2026-08-29. The owner asked for sectioning they could create from the capture screen itself, the way `C` is capture, with the set hint remapped to `H`. Until then the sentence above was aspirational — the only way to declare a divider was `PUT /boxes/<box>` with a whole layout, typed into a field on `#/inventory`, which is a different operation wearing the same words: performed later, from another screen, and needing the operator to remember which card they were on when the divider went in.

**The two halves of that instruction are one design.** Deleting the automatic divider is what makes the key worth having — a screen that invents a boundary every 25 cards does not need a control for putting one in — and the key is what makes deleting it safe.

- **`POST /boxes/<box>/sections` takes NO INDEX.** `store/master.py:open_section` reads `next_index` inside the store lock, so the divider lands in front of the card the next capture will actually take. A client computing it would read a high-water mark across a round trip and send it back — the lost update `next_index`'s own docstring exists to prevent, and at the feeder's measured 623 ms cadence rather than a theoretical one.
- **It is `next_index` and not count+1**, which matters exactly where D10 already matters: a box with permanent gaps in it. A count would put the divider in front of a card that will never be captured.
- **An undeclared box materializes `[1, at]`, not `[at]`.** `check_sections` requires a layout to start at index 1 and is right to — there is no card before the front of a box. Nothing is invented by that: section 1 already started at card 1, and this is the first time anything needed to write it down.
- **It logs `resectioned` through `set_sections`**, the event the dividers editor already writes, carrying both layouts. A new event name was considered and rejected on D26's evidence: this store has already been bitten by a state and a history event sharing a word.
- **Three refusals, each in its own code**: `section_empty` (pressed twice with nothing captured between — the divider you want is already there, and an empty box takes this too, since card 1 is where the first section starts), `section_ahead` (a divider already declared past the next card, which the dividers editor allows and this cannot append behind), and `box_closed` (a sealed box takes no more cards, so a section with none to come is a divider in front of nothing).
- **No confirm and no undo, and neither is an oversight.** Nothing is spent and nothing is destroyed; the remedy for a mis-press is the dividers editor, which is where a wrong layout is corrected anyway, and `resectioned` carries the layout it moved from. A dialog on the screen the owner shoots a box from at feeder pace is what `docs/DESIGN.md` refuses in as many words.

**The set hint is `H` now, and the swap cost nothing else.** `S` was on a field an operator opens a few times a run and was wanted for an act performed at the box. The option alphabet (`docs/DESIGN.md`) is every key this screen has not spent, so it lost `s` and gained `h` — and because `h` sorts after `e`, the first thirteen option keys are `1234567890ade` before and after, which is why `app/tests/capture-claims.spec.ts` pins them and stayed green.

### The rule governs the INDEX; the label is a view

These were the same sentence while sections were a global constant and they are not any more. **The index is the identity**: assigned once, surviving a sale as a permanent gap, and nothing renumbers it — unchanged and absolute. Section and Card are a *rendering* of that index against the box's current divider layout, so moving a divider relabels every card behind it without touching a single index.

**Boundaries are freely editable from any screen, and labels always recompute** — the owner's ruling, chosen over freezing a section once a card sits in it. The argument for it: correcting a wrong layout is the whole point, a label was never printed on anything, and the alternative leaves the model permanently unable to describe a box you physically re-divided.

The cost is recorded here rather than designed away, because it is real: **a mis-tap relabels a filled box and nothing flags it**, and the Fulfiller walks to the wrong slot with no error to see. Mitigated by a `resectioned` history event carrying both layouts — not by restricting the operation, which was the other option and which the owner declined. If that failure ever actually happens, the fix to reach for first is a confirm on an edit that moves a divider with cards behind it, not a return to freezing.

### Undo deletes the record; it does not tombstone it

Settled 2026-08-12, before step 7 built it. A tombstone would be a third thing the store has to explain — not captured, not sold, still occupying a position — and every reader would have to learn it. A deleted record is a card that was never captured, which is exactly what the operator means by undo.

**This decides index reuse, which is otherwise the allocator's most surprising behavior.** `next_index` is a high-water mark, `1 + max(index in this box)`, so deleting the newest record hands its index straight back to the next capture. That is the correct outcome and not an accident of the implementation: the position was assigned to a photo that no longer exists, and burning it would put a permanent hole in a box over a mis-tapped button.

**The box-number allocator is a different rule and is not this one** (D20, amended 2026-08-25). `store/master.py:next_box_number` hands out the lowest free integer rather than a high-water mark, because a box number names an object on a shelf and nothing about it is a position a card was assigned to. Cross-referenced here so the paragraph above is not read as a rule about every allocator in the store: this one governs the INDEX inside a box, and that is the only thing it governs.

**Undo is the newest capture in a box, never an arbitrary one.** Deleting a record from the middle leaves a gap the high-water mark cannot reuse — indistinguishable, later, from the permanent gap a sale leaves, and the rule above says those mean different things. Restrict the operation rather than teach the allocator to fill holes: D10's first paragraph is what makes a printed position label worth trusting, and nothing that renumbers may exist.

**The capture screen shows ten of them as of 2026-08-29, and the rule above is why a row is not a delete.** The owner asked for `U` to undo the most recent capture but for the control to be a growing queue — the ten most recent captures, clickable from the sidebar. The control was one card and one button; it is now the session's ten most recent captures into the current box, newest first, every row its own control.

**Pressing row N undoes N cards** — that row and everything captured after it. It is the same route N times, newest first, which is the only thing the sentence above permits: card N-1 is not the newest until card N is gone. A per-row delete of a middle card would be ruling 1's mid-box remove, which slides every higher card down one index — and putting that on this list would renumber the very rows it was pressed from, which is the defect D37 refuses for the review screen's worklist in as many words. That operation exists and stays on `#/inventory`.

**The count is drawn on the row, and that is the whole of the guard.** `docs/DESIGN.md` makes capture-undo the one place a destructive act gets no dialog, on the argument that the deleted photo is of a card still within reach of the hand that fed it — an argument that is about ONE card. A press that deletes five needs the five to be visible before it, not a confirmation after it, so the row carries the number of cards it removes. It is also the row's ordinal, which is what lets one chip say both. The top row carries `U` instead, because that is the key that fires it.

**A walk that is refused partway stops there and says how far it got.** The next delete is only legal because the one before it succeeded, so carrying on would aim at a card that is no longer the newest. The count is the only thing left that says where the operator is: the cards that went and the cards that did not have both left the list either way.

**The stack is this session's captures, and where the server is ahead it collapses to one row.** A capture that committed and lost its response, or a capture the other device made into the same box (D13 permits both), leaves the store holding cards this session never took — no label, no photograph, no count for them. Offering to undo *back to* a row underneath them would be offering to delete somebody else's captures sight unseen, from a list that cannot draw them. So the depth is exactly one until the two agree again, which one ordinary undo restores.

A sale is the opposite case and is unchanged. `sold` is a state, the record stays, and the gap is permanent.

### Three owner rulings, 2026-08-23, each narrowing a line above

1. **Mid-box delete WITH contiguous shift exists now, bounded.** *Nothing that renumbers may exist* is overruled for exactly one case: deleting a junk capture mid-box when **every higher-index card in that box is still `captured` or `identified`, with no listing hold** — the physical truth of pulling a card out of a contiguous stack, where the cards behind it really do slide forward. The boundary is what keeps the old rule's reason alive: a sold or retired gap above the deleted index refuses (`renumber_blocked`), because shifting across it would close a gap that means something, and a listed card's row is already in a file that names its position. Photos and sidecars are renamed inside the same locked operation; a `renumbered` history event maps every old index to its new one, so the log stays true across the shift.

   **That reason weakened with D58 and the refusal stands anyway.** The box already closes up over a departed card on every screen, so there is no gap left for a shift to close — but this route moves the STORED index, which a photograph and an import file are named by, and the records it would move across are departures and commitments. Relaxing it is its own decision and has not been argued. What was corrected is the sentence the screen recites, because a refusal explaining itself with something nobody can check any more teaches an operator to read past it.
2. **Capture-undo narrows to `captured` alone.** *Undo at `identified` is ALLOWED — only the identification fee is lost* is reversed: once a card has been identified it has made it into inventory proper, and the capture screen's undo may not reach it. The remedies for an identified card are the ones built for it — re-shoot, retire, or the mid-box delete above where its bounds allow.
3. **A whole box may be deleted** — records, photos, sidecars, queue entries, cache — gated as the genuinely destructive action it is (`docs/DESIGN.md`'s clause), and refused while the box holds any sold, retired, or listing-held card: those records are history and commitments, not clutter.

## D11 — Listing path is a catalog join, never a from-scratch CSV

**A listing is a catalog join against the export, never a CSV written from scratch.**

TCGplayer flow: Pricing tab → Export Filtered CSV (All Printings, so one file covers every variant) → pipeline fills fields → Import to Staged → review → Move to Live. Rows match by the `TCGplayer Id` SKU, which is never modified.

## D12 — Scope

**Modern era only (SWSH/SV), English, all Near Mint (hardcoded).** Vintage and WOTC condition strings — 1st Edition, Shadowless, Unlimited — are a spec change, not a parameter.

**Those two sentences went missing between 2026-08-13 and 2026-08-23**, dropped by the motion-trigger commit rather than by any decision, leaving an entry titled *Scope* that stated no scope, two paragraphs referring to blocks and a parenthetical with nothing above them to name, and the Vintage/WOTC rule spliced onto an unrelated paragraph. D15 and D26 both cite this entry as though it said what it says again now. Restored verbatim from `e955afd` rather than rewritten, because the surrounding argument was built against that exact wording.

**Gate B ran entirely outside the two blocks named above, and nothing noticed.** The 53 cards of 2026-08-22 were `ME01: Mega Evolution`, a block later than SV, and they went through capture, identification, join, emit, import to Staged and reconcile without a scope question arising — because nothing in the tree enforces the parenthetical. The only code citing this entry for scope is `pipeline/variant.py`'s `CONDITION_BY_FINISH`, which hardcodes the Near Mint strings; there is no set or era filter anywhere. Read `(SWSH/SV)` as the blocks that existed the day this was written, not as an allowlist.

**Whether modern era is open at the top end is unsettled, and it is the owner's call.** Recorded rather than answered, because a passing gate is evidence that nothing broke rather than a decision that every future block is in scope. It matters in one place today: D15's mirror-scope paragraph reads this entry as the enumeration `SWSH/SV` when it sizes a narrowed image mirror at ~4.8 GB, so narrowing the mirror on that basis would exclude the only era this project has ever run against. Settle both lines together or neither.

## D13 — Stack

Vite + React web app in a desktop browser. Python capture server + batch script. Inventory state is server-side JSON on the Mac, read and written through the capture server, so the owner's and Fulfiller's devices share one truth. Photos on Mac disk, box-keyed by capture position — see D6. Build environment is Claude Code on the Mac; code never lives in chat.

**The Mac stays the one truth, and the owner is keeping a port open** (recorded 2026-08-23 at their instruction, when asked whether to host the capture server somewhere persistent). The answer for now is no: the photographs and `inventory.json` live on this machine, and hosting means moving 682 photographs and the store off it — which is not a deployment detail but a different product, with backups, secrets and uptime attached. Remote access, when it is wanted, is a tunnel to this machine and needs no code change.

Recorded rather than left implicit because the owner said it may eventually become a product for other people. Nothing in the design is being bent toward that today, and this paragraph is the marker so a later session knows the single-operator assumption is a CHOICE with a known exit, not an assumption nobody examined. The pieces that would have to move are named where they are: this entry (one truth on one disk), D5 (two personas on two devices), and D24's opsec rules, which assume a machine one person controls.

**The rig's camera path, recorded 2026-08-13 because nothing in this repo ever said it.** A Sony RX100 VII or A7C, over HDMI into an Elgato Cam Link 4K.

The consequence is why this belongs in a decision rather than in a spec's prose: **the Cam Link presents the camera to the browser as a plain UVC webcam.** It is not distinguishable by kind from a laptop's built-in camera — only by its device label and id. That is exactly why `facingMode: "environment"` was v1 bug 3, and it is why the device picker is a requirement rather than a nicety: there is no camera-facing hint to select on, and the wrong guess photographs a whole box through the wrong lens.

**The Cam Link hands the browser a landscape frame however the camera is mounted.** The second consequence of the same path, measured at Gate B on 2026-08-22 and the largest single defect that run found. The rig mounts the camera on its side so a portrait card fills the portrait field — the right call by the frame-tight rule below — and the stored photo came out sideways anyway. Haiku misread 45 of 53 of them into the review queue with names and numbers both garbled; `docs/GATES.md`'s Gate B section carries the rest of the counts. It belongs in this entry for the reason the paragraph above gives: nothing about the capture device reaches the browser except its label, its id, and the frame it sends, so mount orientation is not a thing the app can detect.

**The rotation is two choices, not four (owner, 2026-08-24).** It was `0 | 90 | 180 | 270`, and offering all four was offering two answers that are never right. The geometry above does not vary: the camera is mounted on its side and the Cam Link sends landscape regardless, so the stored photograph is upright only after a QUARTER turn — 90 or 270 depending which way the body faces. 0 leaves every card sideways; 180 leaves it sideways and upside down.

**And 0 was the fallback, which is the half that actually bit.** The reader answered 0 for a missing, malformed or out-of-range value, so every new browser and every cleared device started in the state that produced this entry's own disaster — 45 of 53 misread, names and numbers garbled. It answers 90 now, and a stored 0 or 180 from before today migrates to it rather than being obeyed. A guess that is right half the time beats one that is wrong always, and the other half is one keypress away on a control whose value is printed in the sidebar.

The narrowed union did the rest of the work by itself: TypeScript found the landscape stage, the landscape frame and the landscape undo thumbnail as unreachable branches, and all three are deleted rather than left permanently true.

The fix is a rotation remembered per device and applied at capture time rather than in the identify path: `app/src/useCamera.ts` holds the setting and `app/src/encode-worker.ts` turns the frame before it is encoded. Rotating there corrects the model, `geometry/`'s crop bands and the review queue's judging photo at once, where a fix in `identify/` would have left a sideways photo on every screen that shows one. The live preview is deliberately left as the camera sends it — the stored photo is the record that has to be right, and the last-capture panel shows it, so one capture confirms the setting.

**The camera is not driven directly, and that was asked rather than assumed.** Tethered capture over USB — Sony's Camera Remote SDK, or `gphoto2` in PC Remote mode — buys full sensor resolution at a cost of roughly one to three seconds per frame, a platform-specific native dependency, and a refocus per shot. Sony's Imaging Edge Desktop is ruled out before any of that by `CLAUDE.md`: no manual third-party UI step inside the autonomous pipeline.

**Frame the card tight in the 4K field; that matters more than the sensor.** The reasoning is in `docs/specs/capture-app.md` and it corrects a simpler argument that was nearly recorded here: resolution is *not* irrelevant just because `identify/images.py` downscales the whole card to 1568px. The crop-retry path in `geometry/crop.py` upscales the collector number to at least 600px, and it can only enlarge pixels that were really captured — which is the failure mode T1's recorded misses actually have. Tight framing at 4K recovers most of what tethering would have bought, for free, and glare on the number corner is unrecoverable at any resolution.

**"Server-side JSON" was reopened by D88 on 2026-09-01, and the rest of this entry stands.** The first sentence above names JSON and never argues for it — it is the one word in this entry that was a default rather than a decision, and `store/__init__.py` spent three weeks forbidding a SQLite store on this entry's authority in words this entry never used. What D13 actually decides is unchanged: one truth, server-side, on this Mac, read and written through the capture server so two devices cannot disagree. D88 changed the file format behind that sentence, on an argument about transactions this entry did not have, and it cites this paragraph rather than restating it.

## D14 — Two tracks, one rig

**One rig serves two tracks: singles and code cards share hardware, never schemas.**

Shared: physical rig, capture server, capture app shell (mode toggle), photo storage, operating rules. Separate: schemas, identification, sales channel, fulfillment.

Sequencing: codes rides the shared foundation (harness → rig → server → app shell), serves as the feeder's shakedown cruise, and may sell manually on eBay early. Its delivery automation is gated on singles Gate B.

## D15 — Catalog data is vendored, not fetched

The pokemontcg.io dataset is a committed snapshot of the maintainer's own `PokemonTCG/pokemon-tcg-data` repo. Nothing calls `api.pokemontcg.io` at runtime. Zero rate limits, zero latency, zero dependency on someone else's uptime. Build-order step 9 — after Gate B, because no production code reads this data today.

**Why a snapshot is safe here, when a pricing snapshot would not be.** D8 routes every price through the TCGplayer export, and the raw repo carries no price block at all. What is left — set ids, collector numbers, printedTotal, names, rarity — is fixed the day a card is printed. Staleness therefore has exactly one form: a *new* set is missing. That fails loudly as an unknown set id, never quietly as a wrong price. Refresh is a `make` target run monthly that records the upstream commit SHA, so a T1 score is attributable to a catalog revision.

**SQLite, not Postgres.** ~20k rows, read-only after load, one machine. Every Postgres advantage is absent: no concurrent writers (D13's two devices share one truth *through* the capture server, so there is still one writer), no network access, no indexing at a scale SQLite strains at. Against that it adds a service that must be running for `make harness` to pass — the exact class of dependency this entry deletes. `sqlite3` is stdlib, so `requirements.txt` keeps its property of naming what it deliberately omits.

**Card records carry no nested `set` object.** Unlike the API response, the set is implied by the *filename*, and `printedTotal` lives only in `sets/en.json`. The join key is `zfill(3)(number) + "/" + printedTotal`, so joining card→set by filename is the one detail a loader must get right. There is no `tcgplayer` block either; see D8 for why that is fine.

**The image mirror's path is a knob, because of its size.** A full mirror is ~16.7 GB (measured: 834 KB average across 197 hires PNGs) against the 160 MB of eval images held today, which is large enough that which disk it lands on is a choice worth having. Path is overridable through `PKMNSCAN_IMAGE_MIRROR`; `harness/images/` moves with it rather than being left behind as a second copy. Mirroring at all is the point — `images.pokemontcg.io` is the piece most likely to throttle or disappear, and it is the one piece the JSON repo does not cover.

**Mirror scope is a knob with a default, not a constant.** Full catalog is the default. D12 scopes the product to SWSH/SV, which would cut the mirror to under a third (~4.8 GB) — recorded so that narrowing it later is a decision rather than an oversight.

**Upstream publishes no license file.** Private, single-operator use only. Recorded so no later session assumes redistribution rights that were never granted.

**A defect this erases.** The current fetch requests `pageSize=250` with no pagination loop, but sv1 has 258 cards, sv4 266, sv8 252 — and the banked `sv1.json` holds exactly 250 records, so sv1 is truncated today. Low severity: the manifest pins the selection, so committed scores stay reproducible and the effect is sampling bias rather than a wrong number. A local file has no page size.

## D16 — The docs are checked mechanically; the prose is checked by asking

**Every path, target, threshold and id in the markdown is checked by a script; the prose itself is checked by a model, and only the first may block a commit.** This repo's markdown carries its architecture and the reasoning behind it, and until `scripts/docs-audit.py` existed nothing verified a single line of it. Every path, `make` target, subcommand, test id, threshold, decision number and env var in it was true only for as long as someone remembered. That is the same argument `docs/GATES.md` makes for the harness — without it, *looks done* is the only available signal — applied to the files that tell the next session what done means.

### Three layers, split by how knowable each finding is

1. **Mechanical** — `scripts/docs-audit.py`, stdlib-only, run by the pre-commit hook and by `make docs-audit`. Every check is deterministic, and **blocking is the default**: a finding is mechanical when a reference is provably wrong — a path that does not resolve, a `make` target that does not exist, a threshold that disagrees with `docs/GATES.md` — and it exits 1, because there is no judgment to defer.

   **A finding prints on exit 2 instead of blocking when judging it needs context the script cannot have.** A decision id cited in a `.py` comment could plausibly become a variable name one day; code that changed beside an unchanged doc is a question, not a defect. A false positive that blocks is worse than one that prints.

   **Neither the roster nor its count is restated here.** `make docs-audit` names every check it runs, each row marked blocking or advisory, and that output is the register. This paragraph used to publish the count, and keeping one restated number honest cost more machinery than any other check in the file — all of it guarding a fact nothing downstream consumed. Deleting the claim deleted the need. D18 records the general rule.

   **A check is named, never numbered** — the same rule D17 sets for the repo-map check, enforced for all of them. Positions moved once already; the report's labels are the names.

   **And a decision id names one entry, which nothing asserted until 2026-08-30.** `docs/DECISIONS.md` carried THREE entries numbered `## D50` at once — the feedback states, the Cmd-arrow nav and the photo URL — written by three sessions that each took the next free number against the same base and all merged. Every row of this audit was green the whole time.

   **The reason is the shape of the reader, not an oversight in the roster.** `decision_headings` returned a SET, so three headings collapsed to one element: the published count was of DISTINCT ids and read 51 over a file holding 53, and the citation scan is satisfied by a heading EXISTING rather than by exactly one existing. A reader that collapses its input cannot report on what it collapsed, so the list is now the primitive and the set is derived from it.

   **What a duplicate costs is worse than an untidy file, which is why this blocks.** `governed_by` in `docs/map.py`, D17's decision-context hook and every `(D50)` in a comment all resolve an id to an ENTRY, and with three candidates they resolve to whichever is found first — a citation that is wrong in no way anything can see, because it points at a real heading, just not the intended one. Two headings carrying one id is provably wrong however the file got that way, which is this entry's own test for mechanical.

   **The three were renumbered by POSITION IN THE FILE rather than by who landed first**, so `docs/DECISIONS.md` stays ascending and no entry's 200-line block had to move: the first keeps D50, and the others became D51, D52 and D53. That also left the most-cited of them untouched, which is the smaller half of the reason and the one that made the change reviewable.

2. **Coupling** — the same script, `--staged`: code changed under `pipeline/`, and `docs/specs/batch-script.md` did not. **Exit 2 prints and allows.** Fires only above 20 staged lines, so a typo fix stays quiet.
3. **Semantic** — `/docs-audit`, a model reading prose against the diff. Never a gate: it costs money, it is not reproducible, and this project does not let a non-deterministic thing decide whether work is done.

**Why the coupling question does not block.** Stopping a commit over a question teaches you to reach for `git commit --no-verify`, and `--no-verify` also switches off the three opsec rules in the same hook. Trading a code-card bearer-instrument guard for a prose reminder is a bad trade, so layer 2 asks and gets out of the way.

Worth being exact about what `--no-verify` costs, because it is more than it was: those three rules run **only** at commit time now. Their `PreToolUse` twin, `scripts/guard-opsec.sh`, has been disabled in `.claude/settings.json` since 2026-08-03 — it blocked any write containing a code-shaped literal, including placeholders in prose about the format, and cost two blocked writes in one session. Fixtures stay covered while it is off by the `permissions.deny` rules; the code-card literal does not. **Revisited and re-enabled 2026-08-23**, when D24's build made the condition true: the narrowed pattern blocks by shape (stands alone, mixes letters and digits, no all-repeated group), passes byte-exact reconstructions of both historical false positives, and fails open on its own bugs — so `--no-verify` no longer switches off the only opsec layer, and the commit-time rules are again the backstop rather than the whole guard.

### A git worktree inside the tree is another branch, and the audit does not walk one

Added 2026-08-29. Concurrent sessions check worktrees out under `.claude/worktrees/<name>/`, which is a full source tree of a DIFFERENT branch sitting inside this one. The walk found them, so the audit was checking one branch's prose against another branch's code and reporting the disagreement as a defect in yours. Observed: a worktree's `CLAUDE.md` documented a `worktree-setup` target, real on its own branch, and the make-targets check failed a commit on `main`, which has no such target. **Two branches are allowed to disagree; that is what a branch is.**

**It is pruned twice, by name and by asking git, and the two cover different things.** `worktrees` in `SKIP_DIRS` catches the convention and keeps working when git does not answer. `nested_worktrees()` reads `git worktree list --porcelain` and prunes any checkout under the repo root whatever it is called — verified against a worktree named `zz-scratch-wt`, which no name rule could guess: zero files walked, audit clean. It fails open exactly as `ignored_paths` does, because a discovery helper that can abort the audit is worse than one that occasionally walks too much.

**This is not the gitignore filter and neither subsumes the other.** That filter stops a finding being *reported* for local state; this stops a foreign tree being *enumerated*. The finding here was against the make-targets check, which never consults the filter. `--self-test` covers the staged path; the on-disk path needs a real repository with a real worktree in it and was verified by hand, which that case says in as many words rather than implying coverage it does not have.

### Nothing on the audit path can write

The script opens, compares, prints, and sets an exit code; it parses with `ast` rather than importing, so it does not even run project code. Its only writes are inside `--self-test`, into a temporary directory it creates and destroys.

**`--self-test` therefore runs in `make check` and never in the git hook** (settled 2026-08-24). It is the one mode of this script that writes, and D18 forbids a writing thing on the path that decides whether a commit proceeds; `make check` is invoked by a person on demand, so it is not that path. Until then nothing ran it at all, and it had gone red without anyone noticing — a stale fixture in `tested_by reach` had stopped being false while every commit stayed green. `docs/DEBTS.md` carries the account. The residual gap is named there too: `make check` is not automatic either, so a red self-test still surfaces only when somebody asks.

Adding a `--fix` flag is a change to this entry, not a configuration knob. The reason is the failure this entry exists to prevent:

> **A blocked commit is reported, not resolved.** Never edit a doc for the sole purpose of getting a commit through.

An agent that can edit the docs to satisfy its own gate will do exactly that, and each edit will look reasonable. The docs stop being a record of what was decided and become a record of what was convenient — and unlike a failing test, nothing downstream ever notices. That is also why `/docs-audit` shows every proposed change in one table before touching anything, and never stages or commits: the owner's own `git diff` is the last link in the chain.

**The docs audit is not a harness test, and must not become one.** Putting it in `harness/run.py:TESTS` was considered and rejected. The harness runs behind the `Stop` hook (`scripts/stop-gate.sh`), so a docs test there would fire at the end of every turn, including turns that touched no markdown at all. The trigger is commit-time and on-demand by choice.

This paragraph used to make that point by naming the number the docs test would have taken, which stopped working the moment a real test needed a number. T7 is now the store, server and command-seam test (`docs/GATES.md`), and it is unrelated to this entry. The rule here was never about a number.

**The allowlist is self-cleaning.** `scripts/docs-audit-allow.txt` records things the docs name before they exist — `PKMNSCAN_IMAGE_MIRROR` was documented by build-order step 9. The audit **fails when an entry comes true**, which forces the line out at that moment. Same instinct as `stop-gate.sh` arming on the absence of `NOT_IMPLEMENTED` markers rather than on a toggle: a list that only grows becomes a list nobody has read since.

**A threshold is published, not restated.** Each test's `PASS_CRITERIA` must appear word for word as the `- **Pass**:` line of its `### Tn` section, and layer 1 blocks a commit where they disagree. **Reconciliation runs from the test to the gate.** The test is where a threshold is argued about and changed; `docs/GATES.md` is where it is announced. Rewriting a test so a doc-checker goes quiet inverts that and makes the test worse to please a tool.

Five of six had drifted before this was enforced, which is the case that decided the direction: those tests were changed deliberately and approved, and the change simply never reached the markdown. An approved change that does not reach the doc is the failure this whole entry exists to stop, so it blocks rather than asking.

**One known gap, recorded so a green report is not misread.** Layer 1 proves references resolve and thresholds agree — not that a paragraph is true. Treat a clean mechanical run exactly as `docs/GATES.md` treats a green T1 and T6: it means the checkable part checks out.

## D17 — The repo describes itself in `docs/map.py`, and the map is audited

Two questions kept costing a full search to answer: *what is built and what is TBD*, and *which settled decisions govern the file I am about to edit*. Both were already answered in prose — `docs/GATES.md` has the build order, this file has the rulings — but prose has to be read whole before it can be trusted, and the first question alone cost a subagent sweep and roughly 285k tokens in one session.

`docs/map.py` answers both in one Read: build-order status, gate status, and per-component `does` / `status` / `governed_by` / `tested_by`. Pure literals, no imports, read with `ast.literal_eval` by everything that consumes it.

**Data, not another markdown section, because it has three consumers.** A human or agent reading it once; `scripts/docs-audit.py`'s repo-map check, which verifies every claim in it — named rather than numbered, because a positional index re-drifts every time a check is added, and this one already had; and `scripts/decision-context.py`, the `PreToolUse` hook that names the governing decisions before a file is edited. Prose serves the first well and the other two not at all.

**It is audited exactly as hard as it is trusted.** An index that drifts is worse than no index, because it is believed. The repo-map check fails when a `built` path is missing, when a `planned` path has quietly arrived, when `governed_by` cites a decision with no heading, when gate status disagrees with `docs/GATES.md`, and — the rule that does the real work — when a source file exists that no entry mentions. Adding a module without touching the map fails the commit. That orphan rule is the difference between a map and a stale map.

**`governed_by` is a superset of the citations in the file's own comments,** enforced in the same check. The code already said `D9` in `pipeline/pricing.py`; the map may add D8, which the file never names but which decides where its prices come from. It may never know *less* than the code does.

**The hook is advisory and silent by default.** `scripts/decision-context.py` exits 0 unconditionally — bad input, missing map, its own bugs — and prints nothing for files no entry covers. It summarizes each decision by lifting the entry's own bolded lead-in sentences out of this file, so a summary cannot drift from the decision it summarizes; nothing is restated by hand. It emits `additionalContext`, never `permissionDecision`: `"allow"` would auto-approve every Write and Edit in the project.

Precedent for the caution: the opsec `PreToolUse` guard over-triggered and was disabled within a day. A hook that speaks on every edit gets muted, and a muted hook protects nothing. The first draft of this one merged each package's decisions into every module and told you `pipeline/pricing.py` was governed by D2, Haiku vision — true of `pipeline/`, useless there. Module entries now stand alone.

**Known limit.** The hook depends on a payload shape that has moved between Claude Code releases. If a release ignores `additionalContext` the JSON is printed instead, so the failure mode is a lost nudge and never a blocked edit — and `CLAUDE.md` points at `docs/map.py` directly, which needs no hook at all.

## D18 — A generator may write. Nothing that writes may gate a commit.

D16 forbids the audit writing, and gives the reason: "An agent that can edit the docs to satisfy its own gate will do exactly that, and each edit will look reasonable." That argument is about a *path*, not about a script, and D16 states it as a property of the script — which leaves a loophole wide enough to drive a build target through. A generator that rewrites a doc from a code constant is not the audit, breaks none of D16's letter, and recreates its failure exactly if it runs inside the gate: `make check` regenerates, the audit passes, nothing fails, and the doc now says whatever the code said.

**Nothing that writes may run on the path that decides whether a commit proceeds.** D16's "Nothing on the audit path can write" is one instance of this rule, not the whole of it. Generation is permitted; generation inside the gate is not.

**A seam is permitted only where a file's job is reference, and the permitted locations are listed here by name.** The list is currently empty. Adding to it is a change to this entry, argued on its own terms — not a judgement call made while implementing something else. This is the rule that keeps generation from spreading into the files agents read as argument, and it is stated early because it is the one most likely to be eroded quietly.

**The list above is empty, and that is the finished state, not an unfinished one.** This entry was written while considering a generator for one specific number, and the act of writing the seam rule is what showed the better answer was to stop publishing the number at all. Nothing in this repo generates anything today. Read this entry as a guardrail placed across a loophole D16 left open — not as an invitation to use a mechanism sitting ready. A later session finding an empty list has found the intended condition. Adding the first entry means arguing that a fact must be published in prose *and* cannot be hand-maintained, and that argument has not yet been made once.

**The test for "carries an argument": could a later session reasonably disagree with this line?** A count, a status word, a list of registered names — verifiable, nothing to disagree with. A threshold, a rationale, a trade-off — arguable, and therefore never generated. A second test, applied together with the first: if the span were replaced by its bare value, would the surrounding paragraph still mean the same thing? If not, the fact is load-bearing inside an argument, and the seam would cut it out of its reasoning. Prose that explains *why* is never a generation target, no matter how mechanically derivable the number inside it is.

**The split is write-time versus check-time.** The docs-gen make target writes and is invoked by the owner. The pre-commit hook and `make check` verify freshness and fail — they never regenerate. Verification is not free: it means computing what the span should say and comparing, which is the generator's logic running on the audit path minus the write. Budget it as its own cost. Generated output is committed, so the owner's own `git diff` remains the last link in the chain, exactly as D16 requires for the semantic pass.

**The generator is stdlib and reads with `ast`, for as long as freshness is checked in the git hook.** The hook runs `python3` with nothing installed, so a generator whose freshness check runs there cannot require a package. That rules out `cog` — otherwise the right tool, actively maintained, with a check mode built for exactly this — because it is a PyPI dependency and it executes the embedded Python, which would make the hook depend on the import graph staying free of third-party modules at module scope. Nothing enforces that today; `ast` does not care. **This constraint is contingent, not permanent: if freshness verification moves to CI, the stdlib rule stops binding on the generator and `cog` becomes viable.** Recorded so a later session reads this as a consequence of there being no CI today, not a standing judgement about the tool.

**What this supersedes.** D16's paragraph beginning "Nothing on the audit path can write" stands unchanged as a statement about the audit. This entry generalises its scope: read that paragraph as the specific case and this rule as the general one. A fix flag on the audit remains forbidden by D16, and this entry does not soften it — a generator is a separate program with no findings, not the audit gaining a write mode.

**The failure this prevents:** a generator on the commit path turns every wrong constant into a confidently published sentence, with the audit green and no diff a reviewer would question. Checking lets two things disagree in public. Generating makes one thing true everywhere, including when it is wrong.

## D19 — Motion capture: live fire behind the seam, a trace for tuning, video for neither

**The auto-capture trigger fires live, per card, through the same `POST /capture` a key press uses. Recording the run to video and extracting frames afterwards was worked through and rejected as a capture path** — not on image quality, which is a configuration choice, but because segmenting a tape into per-card frames IS the motion state machine run offline: it avoids none of the tuning, while giving up the position↔photo binding `allocate_capture` makes inside the store lock at the instant of capture, D10's undo (whose whole safety argument is that the deleted photo is of a card still in your hand), and §5.5's halt-at-the-moment-of-failure. What video genuinely offers — re-runnability while tuning — the 64x36 luma trace offers at a thousandth of the bytes, so the tape is a debugging instrument for the rig session at most, never a photo source, and deleted once parameters sit on a plateau.

**The card-presence gate reads a quantile, not a mean, and a second rig is what proved it (2026-08-29).** `cardLumaFloor` was the mean ROI luma, and a mean is a statement about the whole watch region rather than about whether a card is in it. Those coincide only while the card FILLS the region — which is what the rig this was tuned against happened to do. On the owner's new rig the card occupies part of the region against a dark surround, so the mean is dominated by background:

    empty stand    mean 27-30    bright quantile 62-69
    settled card   mean 62-86    bright quantile 125-236

**The floor of 90 sat above both means**, so the gate could not fire at any brightness and no relighting would have fixed it — the failure is geometric, not photographic. One session settled twenty cards correctly and refused every one; the next settled fifteen and fired twice, both on a static frame before the feeder started. **Motion and settle detection were never at fault**, which the traces show plainly: every card was found at the feeder's cadence.

**The constant does not move and neither does any other.** 69 against 125 leaves 90 where it was, and a card that fills the region has a quantile at least as high as its mean, so Gate B's ~172 still passes. Re-scored offline through the fix — the traces exist for exactly that — the two sessions go 2 fires to 15 of 15, and 0 to 7 on the under-lit one, with the empty stand still refused. `CARD_QUANTILE` is 0.9 rather than a maximum because a specular highlight, a lamp in shot or one hot pixel all carry a maximum and none is a card.

**This is the paragraph below working as intended, and also its limit.** Every parameter here is derived from a measurement — but the measurements came from ONE rig, and what this found is that a constant can be right while the STATISTIC it is compared against is wrong. A second rig is the only thing that could have shown it, and the trace is what let it be diagnosed and fixed without a rig trip.

**Every parameter is derived from a measurement, and the measurements are named where the constants live.** Gate B's recovered cadence (median gap 609.5 ms, robust σ 34 ms, floor 458 ms, the feeder's own ~660 ms), the <250 ms capture round trip, and a worst-case frame-difference SNR of ~20x on the real frames. `docs/specs/motion-trigger.md` carries the full derivation; `docs/GATES.md`'s Gate C section carries the numbers. The thresholds are rig-tunable constants and the rig has not yet tuned them — BUILT is not TUNED, and the 50-card run is where that changes.

**Arming is an act, not a setting.** The mode is session-only and never persisted, deliberately unlike the remembered camera and the rotation chip: a remembered camera cannot take a photo on its own, and a remembered motion mode is an automatic shutter armed by a page load. Every session starts manual.

**A fire the screen declines is counted, on screen, and the halt banner does the arithmetic.** Under a key, a swallowed fire is fine — the finger is attached to someone watching. Under a feeder that keeps delivering, each one is a card that may have passed the lens unrecorded, which is §5.5's exact failure. So motion mode counts every declined fire by reason, and a halt with the feeder running renders the count as the sentence it means: that many cards to set aside and re-feed.

**A jam surfaces and does not fire.** Continuous motion past the stall window reports `stalled` on the HUD rather than capturing a moving card. The other side was argued — "never silently drop a card" favors firing — and loses for v1 because a hand in frame would capture-spam, and a loud stall is not silent. If the rig session shows real cards dying to stalls, this is the paragraph to reopen.

**Undo stays manual forever.** No automatic anything reaches a control that hard-deletes a record, a sidecar and a photo. The motion trigger exists behind the capture seam only.

**The ordering is the owner's, 2026-08-22: motion capture end to end before any other work.** Step 9 (vendor the catalog) was `next` for a few hours and is re-sequenced behind Gate C — it touches no app code, so nothing collides; one `next` is the rule and the owner chose which. This also dissolves the map's old circularity of step 10 being blocked by the gate that IS step 10.

## D20 — A box is an object, and its capacity is retroactive

**A box is a real object in the store with a name, a state and a capacity that is only frozen when it is sealed.** Before this, **there was no box object anywhere in the repo** — `docs/specs/capture-server.md` §5.4: there is no box object anywhere in `store/`, only a flat dict keyed by box and index. A box existed only because a card named one. The consequences were all small and all daily: a box could not be created empty, could not be named, could not be listed on any screen but Capture, and a mistyped number was caught only by the `new_box` flag *after* a photo had been written — which `server/capture_server.py` notes catches the first typo only.

`store/master.py:Box` carries `box`, `name`, `sections` (D10), `state`, `capacity`, `created_at`, `closed_at`. A box is `open` or `closed`.

**Capacity is retroactive, and that is the whole of the lifecycle.** It is not asked for when a box is created, because nobody knows it then. While a box is open it has none, and the honest denominator is the fill so far — a screen saying `#40 of 53` has to also say *so far*, because tomorrow it is 54. **Sealing the box freezes `capacity` at the final high-water mark**, and only then does `#40 of 250` · 16% in become a sentence that is still true next week.

That sentence is the reason the object exists. The owner's ask: a bare position tells you nothing about where to put your thumb; a fraction does, and a fraction needs a denominator that does not move.

**A sealed box takes no more cards.** `allocate_capture` refuses with `BoxClosed` before it computes an index, so a refusal burns nothing. Admitting one more card would make every fraction already drawn from that box wrong by one.

**Sold cards do not shrink a box.** D10 makes their gaps permanent and `next_index` is a high-water mark, so a sealed box's capacity never falls as its contents sell. Re-opening a box sets `capacity` back to unknown rather than leaving a stale number standing.

**Amended by D58: `capacity` is no longer the denominator, and the denominator does shrink.** Every word above stays true of `capacity` itself — frozen at the high-water mark, never falling, cleared on re-open — and what changed is that nothing divides by it. A card's number now counts the cards in the box, so a count over a frozen capacity draws a card at a percentage of a box it is not at: on a 543-card box that has sold 200, `#100 of 543` puts a thumb a third of the way from the card. The denominator is the cards on hand, for a sealed box and an open one alike, and `capacity` records how full the box got.

**The moving-denominator hazard this entry exists to prevent is answered rather than ignored.** What made `#40 of 53` dishonest was a denominator that is DIFFERENT TOMORROW for a reason the operator cannot see; this one changes only when a card leaves the box, which is a thing they did. The `so far` / `sealed` split is untouched and still says which kind of box it is, and a sealed box's identity line carries both numbers (`542 of 543 sealed`) so neither can be mistaken for the other.

**The same argument has a second instance one scale down**, which arrived 2026-08-23 with the section-scale position bar. A section has a denominator problem of exactly this shape: `section_end` is a DECLARED bound taken from the box's dividers, not a count of the cards actually behind it. Box 1's section 3 runs 51..75 and holds three cards, so `card 3 of 25` and `card 3 of 3` are both true and mean opposite things.

The rule, and it turns on which bound is final rather than on the box's lid alone:

- **Settled** — a divider with cards behind it, so the width is a fact. Render the declared width and say **`slots`**: `Section 1 · card 1 of 25 slots`.
- **Growing** — the last section of an open box, the one the next capture lands in, where the end is not a divider but the edge of what exists. Render the fill and say **`so far`**, the same two words this entry already puts on an open box's denominator.

**The caption must name which it is.** A denominator that silently switches meaning between a full section and a half-empty one is precisely the failure this entry exists to prevent, and at section scale it is easier to miss because the number is smaller and the operator is already standing at the right box.

### A box has a name, the name is how it is addressed, and names are therefore unique

Built 2026-08-25. This entry authored `name` as an optional label and nothing checked it, which was right while it was decoration: the number was the identifier, and a second box called `commons` cost nothing worse than a confusing row. The capture screen now finds a box BY name — one free-text field searching number and name together — so a duplicate name is an ambiguous *physical address*. That moves the ambiguity off the key the operator has stopped typing and onto the label they navigate by, which is worse than where it started. `store/master.py:_check_name_free` refuses one as `BoxNameTaken`, which `server/capture_server.py` answers as 409 `name_taken`.

**The name does not reach `Position.label`, and it was built and reverted to settle that.** `app/tests/fulfillment.spec.ts` floors that label at 32px with tabular figures wherever one is drawn, and D31 is explicit that the spec stays unweakened. The name already travels as `box_name` in the place block and is already drawn beside the label on `CardLocations` and `Inventory`, so putting it inside the label bought nothing and spent a hard constraint.

**Folded and stripped to compare, stored verbatim.** `Commons`, `commons` and `commons ` are one box to a person standing at a shelf, so they collide; what is written down is what was typed. It is the same split `pipeline/join.py:number_index_key` draws between a matching form and a stored one, for the same reason — a normalized value written back is a value the operator cannot correct.

**Unique, not required, and that boundary was chosen rather than fallen into.** Requiring a name would invalidate every box registered before today and would break `BoxOps`' own *Name (optional)* create form. Uniqueness is the property that matters once a name is an address; existence is not.

**A rename appends `box_renamed`, carrying both names.** `server/capture_server.py` recorded the absence of this event as a known gap and gave the right reason for leaving it — a name is a label, not a claim the pipeline spends money against — and that sentence stopped being true the moment the name became the address. A rename relabels every card in the box on every screen that draws one, so an unlogged rename leaves no record of what the box used to be called. **This is D10's divider argument at box scale, and it resolves the same way**: D10 chose a `resectioned` event carrying both layouts over restricting the operation, and `box_renamed` carries both names for exactly that reason. The trail is the safety, not a confirm dialog `docs/DESIGN.md` would ban anyway. `ensure_box`'s silent rename routes through `set_name` as well, so a name reached by that path gets the same check and the same line.

**A box number is assigned now, not typed: `next_box_number`, the lowest free integer.** `POST /boxes` takes a name with no number and allocates inside the lock; sending neither refuses `box_or_name_required`. It reads the CARDS as well as the registry, because a box that holds cards and has no registry entry is a real box — `_box_row` renders exactly that case — and handing its number out again would put two boxes' photographs in one directory.

**It is deliberately not a high-water mark, which is the opposite of D10's card allocator, and the two must not be made to match.** `next_index` hands a deleted card's index straight back, because burning it would put a permanent hole in a box over a mis-tapped button. A box number is the other case: it names an object on a shelf, the operator no longer types it, and nothing but the store, the disk and the wire reads it — so the lowest free number is the honest answer and there is no gap for it to close wrongly.

**What this makes stale, named here because the spec is older than the screen**: `docs/specs/capture-app.md` §5.2 said box selection was a list from `GET /status` and that starting a new box is a typed number. Both are overtaken — the field reads `GET /boxes`, and the number is allocated rather than typed — and that section is marked accordingly rather than rewritten, the same way §5.1 was when Pass D landed.

### An empty box is a box, and for one commit it was unreachable

Found and fixed 2026-08-26. `#/inventory`'s box strip was built from the CARD ROWS — `BoxBrowse.tsx:shelvesOf` walked the cards and collected the boxes they named — so a registered box holding no cards produced no row, therefore no shelf, therefore no cell. The strip is the only way to SELECT a shelf, and `BoxIdentity` and `BoxOps` draw for the selected one, so rename, dividers, seal and the whole-box delete were all unreachable for it. Measured on the owner's store the day it was found: **12 of 13 boxes**, including every box they had just created to test with. `Register a box` was a loop — it made a box that immediately vanished.

**It is `CLAUDE.md`'s route-is-not-a-feature rule caught from the far end.** That rule was written for a capability with no control; this is a control, a client function and a tested route, all present and all correct, for a box no screen could be put on. Worth recording as its own shape: the checklist that rule prescribes — route, client function, control on the screen a human would look for it on — was fully satisfied and the feature was still unusable, because nothing in it asks whether the OBJECT the control acts on can be selected.

**And it is a regression with a commit.** `13c397a`, D31's merge, wrote both this strip and retired `#/boxes`, whose entire content was the registry list. The merge carried the cards over and not the registry.

**The registry is unioned in only where nothing is being searched for, and that boundary is the fix rather than a caveat on it.** `shelvesOf` was written so a cell can never lead to an empty list, and that rule is RIGHT about a query: under one, a cell for a box holding no match is a dead end. It was wrong only as a rule about the STORE, where an empty box's empty list is not a dead end but the truth — and it is the only state from which that box can be renamed, sealed or deleted. The walk says so in words rather than rendering a blank column beside a box header.

**The claim editor is not offered over nothing.** `Set claims on all 0 cards in box 6` was a real string on a real screen the moment empty boxes became reachable. It is the one control in `BoxOps` that writes CARDS rather than the box, so it is the only one an empty box can leave with nothing to do. Absent rather than disabled, per `docs/DESIGN.md`.

### The whole-box delete is two presses that both name the box

The owner, 2026-08-26: deleting boxes should require a confirm click, not typing something. D10's ruling 3 gates this operation as the genuinely destructive action it is, and the gate was a typed box number. The argument for typing is worth keeping because it is most of the argument for what replaced it: a yes/no dialog is answered by the same reflex that pressed the button, and this control's whole risk is deleting box 9 while looking at box 95, so a gesture that could not be performed by momentum forced the operator to read which box they were aimed at.

**What it was measured against was eleven empty spam boxes and eleven typed numbers**, in the session that made empty boxes reachable at all. A gate whose cost scales with how many boxes you are tidying up is a gate that gets resented, and a resented gate is read past rather than read.

**So the half that survives is the half that was doing the work: naming the target.** `Delete box 6…` opens the panel and `Delete box 6 permanently` fires it, so the number is printed twice and the second press is on a control that has to be found rather than one sitting under the pointer. What is given up is the momentum guarantee, deliberately and by the owner. **This is still not the *are you sure* `docs/DESIGN.md` bans**: that dialog's confirm says nothing about what it is confirming, and both of these say the box.

**What would reopen it: a box deleted by mistake.** The fix to reach for first is then graduating the gate by what the box HOLDS rather than restoring typing everywhere — an empty box's delete destroys a name and a number, and box 2's destroys 543 photographs. That is one condition on `record.cards`, and it is named here rather than built because the owner asked for the simple thing and no such mistake has happened.

## D21 — Game is a per-card claim, not a mode

**The game is a per-card claim made on the capture screen, never a mode set on the app shell.** Four capture choices — `pokemon`, `riftbound`, `one_piece`, `pokemon_code` — and the picker sits beside Box, Set hint and Finish.

**`game` joins the claim family and behaves exactly like the others**: client state, resent with every capture, written to the record and the sidecar. **Mixed boxes are therefore legal**, which is not a concession but what makes the claim a claim. A shell-level mode would make the game a property of the *session*, and the first time a Riftbound card turned up in a Pokemon box the operator would have to either lie or stop.

**`game` is required and defaults to `pokemon`, and D3's null-means-no-claim does not transfer.** Worth stating because the two look identical and are not. `FinishClaim`'s `null` is meaningful because there is a **ladder underneath it** that infers a finish from evidence — catalog rows, detection, a human. **There is no ladder that infers a game.** A missing game is not *no claim*; it is *no export*, and every consumer below would have nothing to join against. So the field is required, and the default is a read-side backfill for records written before the field existed — never a write-side default.

**This does not discharge D14.** That entry's mode toggle is the *track* axis — singles versus codes, two schemas, two sales channels, two fulfilment stories sharing one rig. `game` is the *product* axis inside a track. `pokemon_code` sits at the intersection and is why both axes have to exist: a Pokemon product line, captured on the singles rig, disposed of down the codes track (D24).

## D22 — Taxonomies are hand-authored per game, and audited so they cannot drift

`pipeline/games.py` holds one entry per game: the exact `Product Line` cell, the ordered `Rarity` cells, the finish enum, the finish→`Condition` map, and the rarity→finish matrix. Pure literals, importing nothing from this repo, so `scripts/docs-audit.py` can read it with `ast` **without running project code** — the same rule `docs/map.py` follows and the audit enforces on itself.

**Hand-authored, never generated.** Every field is ARGUMENT in D18's sense: a later session could reasonably disagree with the stack order of the rarities, or with which finishes a rarity is allowed to claim. D18's seam list stays empty and this entry is not a request to open it.

**Audited in the direction that can be proved.** The audit reads the committed exports and blocks on what is provably wrong — a rarity whose folded form matches an export string but whose raw form does not is a typo and can never false-positive; an export rarity accounted for by nothing is a gap. It only *asks* about the reverse, because absence from one set proves nothing: `Promo` and every pre-SV rarity are legitimately missing from an SV09 fixture.

**Rarity strings render verbatim, the way reason codes do.** A second friendly vocabulary is a thing nothing audits, and the drift D16 exists to catch.

**That state existed for two games and is now occupied by nobody** (measured 2026-08-23). The entry used to say it was "not yet established that TCGplayer carries Riftbound or One Piece as `Product Line` values at all", and that it was the highest-risk assumption in the design — because if it were false, D8 and D11 would have no data and the architecture would change shape. The owner exported all three. **TCGplayer carries both, on the identical 16-column header**, so the join is structurally valid for every product line. The exact cells, which nobody would have guessed:

    Pokemon
    Riftbound League of Legends Trading Card Game
    One Piece Card Game

**Every consumer still refuses on an empty vocabulary rather than falling back to Pokémon's.** A guessed rarity list is exactly what this repo refuses; an empty one that refuses loudly is strictly better than a plausible one that prices wrong. The state stays for the next game added — it is not deleted just because it is currently unoccupied.

**The superset rule collected its first evidence and won, and this is the paragraph to read before ever narrowing the matrix.** `finish_by_rarity["Rare"]` carried `normal` against an SV09 that stocks no plain Near Mint `Rare` — it was the authored-beyond-the-data example this entry and D23 both cited, and the standing temptation was to trim it to what one export proved. The wider Pokémon export stocks **60 plain-NM Rares** (Cosmic Eclipse 38, Crown Zenith 22). Narrowing it would have made two whole eras unclaimable, on a screen where the excluded chip is unselectable and the operator has no way to say what is true.

The canonical unproved case is therefore no longer `Rare`/`normal`. It is One Piece's `SR` and `TR`, authored with `normal` against an export of three sets out of many — and the audit asks about them as questions rather than blocking, which is the whole shape of the rule.

**A third state, `catalogued`, sits orthogonal to `unverified`** (added 2026-08-23 with the `misc` entry). The two describe opposite situations and must never share a flag:

- `catalogued: True, unverified: True` — a real product line nobody has an export for yet. **Temporary, with a remedy**: get the export. Refusing is right, because a guess becomes a price.
- `catalogued: False` — `misc`: the occasional Yu-Gi-Oh, Weiss Schwarz, foreign-language or Magic card, about 1% of stock. **Permanent, and correct.** No export is coming. It must NOT refuse, because refusing on every misc capture would make a legitimate part of the shelf read as a fault, and a real fault would then hide among them.

`misc` carries `product_line: None` rather than `""` — `None` is not a `str`, so the catalog's comparison can never be true, whereas `""` is both a value a row could carry and the value an unverified entry uses. It is captured and located like any card, takes **no identification call** (it is being handled by hand anyway), and carries a free-text operator note instead so it is findable by search. It sits outside D12 on two axes at once — foreign language breaks "English", and the other three are different product lines entirely.

## D23 — The rarity claim does three jobs, and one of them pays for the feature

The capture screen gains a multi-select rarity claim, scoped by the chosen game. It does three things, and they are listed in order of what they are worth.

**1. Cross-check — the new `rarity_claim_mismatch` review reason.** Emitted in the **variant ladder**, not in routing: routing answers *"is this trusted enough to list?"* and the ladder answers *"which row is this?"*, and routing is currently the only pipeline module with no Pokémon in it. It filters the candidate rows to the claimed rarities and reviews when nothing survives — filter-then-contradict, because on a multi-set collision the filter breaks a `duplicate_condition` tie for free.

**This is the job that pays.** T1's recorded misses are `051/197` for `031/197` and `271/167` for `211/167` — *confident* answers, name right, digits wrong. No confidence threshold fires on those. A rarity contradiction does.

**Rung 0 must not consult it.** A human who looked at the photograph beside the candidate rows outranks a claim about the stack it came from. `answered()` already refuses to re-consult metadata and detection, and the failure that taught it is on the record: sixteen answered cards re-deriving their disagreement and re-parking on every join.

**2. Narrow the finish chips.** Offered = the **union** of `finish_by_rarity` over the claimed rarities — union, not intersection, because a Common+Rare stack legitimately holds both plain-NM Commons and holo Rares. Three rules, each of which exists to stop a specific harm:

- **An empty rarity claim narrows nothing.** The screen behaves exactly as it does today. This is the compatibility guarantee that makes the whole feature strictly additive.
- **It never auto-selects, not even when one finish is left.** A claim of `{Double Rare}` leaves only `holo` and the control still rests on `no claim`. Ladder rung 2 (`CATALOG_FORCED`) already resolves a holo-only Double Rare for free, and a manufactured claim makes rung 2 unreachable for every card this rig sees.
- **Excluded chips are rendered and unselectable, not hidden**, so the operator can see what the claim cost them and take it back by clearing the rarity.

**3. Prompt injection — MEASURED AND SWITCHED OFF (2026-08-23).** Built in the user turn because it is per-card, scoped so it could not poison D3 rung 3, pinned under its own `rarity_fingerprint` so the scored default never moved — and then measured with best-case claims for $0.17, where it lost on every watched axis: holdout down 1.5 points, high-confidence misses up two, and the finish distribution hardened against the carve-out sentence itself. `docs/GATES.md`'s T1 section carries the numbers; the switch in `cli/cmd_identify.py` cites them and names the re-enable condition (a rig-photo measurement, `PKMNSCAN_T1_RARITY=1`). Jobs 1 and 2 are what this entry now rests on, which is where it always put the weight.

The original design, kept because the machinery still exists behind the switch: `SYSTEM_PROMPT` already says *"Do not infer the finish from the card's rarity"*, and a careless clause makes it do exactly that — poisoning the one signal that catches a mis-sorted card. Gated behind `PKMNSCAN_T1_RARITY=1` for an A/B, the same shape as the set-hint knob, and **shipped in its own step** so the fingerprint moves once, deliberately, with a re-measured T1.

**The superset rule is what makes unselectable safe, and the two must never be separated.** `finish_by_rarity` is authored as a superset of what any one export proves. SV09 stocks no plain Near Mint `Rare`; a matrix derived from that observation alone would make a legitimate plain-NM `Rare` stack **unclaimable**, and with the chip unselectable the operator would have no way to say what is true. The audit enforces the superset direction — it blocks on an observed pair the matrix is missing and only asks about the excess. **If anyone ever narrows the matrix to one export's observations, unselectable becomes a trap.**

## D24 — Code cards are pooled inventory, not located

Owner's ruling: a code card has **no box, section or card position**. It is a count. An index is acceptable as a key — it is what the photo and sidecar are named after on disk — but it is not meaningful, because the physical cards are disposed of once the code is extracted.

**The seam is one registry flag, `located`**, and it is the concrete form of D14's "two tracks, one rig". `code-card-fork/CLAUDE.md` already said it: *"Codes are fungible pool inventory, not located items. No box, no section, no position. Do not reuse the singles schema."*

- `located: True` — D10 in full. Sequential position at capture, never renumbered, the label rendered everywhere — and since D58 that label counts the cards in the box rather than the slots, which changes what is rendered and not this flag's meaning.
- `located: False` — `allocate_capture` is unchanged, because the record still needs an index to key its files. But **`Position.label` is never rendered**: not in the review queue, not in a run report, not in the pull preview. **Non-located cards never enter the Fulfillment view or the pull flow**, because there is nothing to walk to, and that is asserted in `app/tests/fulfillment.spec.ts` rather than left to prose.

**Quantity is the unit, and the pipeline already computes it.** D7 aggregates by SKU with `Add to Quantity` = copy count. The count the owner wants is a thing the join already produces — surface it; do not build a second inventory.

**D10 and the fork's C3 do not conflict, and the reason is worth having in one sentence:** D10 positions a piece of cardboard, C3 pools a code string. Two records, two primary keys, joined by the position key.

**Disposal is a terminal state shared with Someday's `removed`.** A code card whose code has been extracted leaves inventory permanently — record kept, gap permanent, exactly `sold`'s shape. Someday already carries the same need for a single card pulled out, damaged or given away, and calls the alternative *"a sale record that lies"*. **Build them as one state, not two.** It is not a tombstone in D10's sense: D10's refusal was about *undo* inventing a third thing the store must explain, and `sold` already proved the state-machine shape.

**Channel is a disposition, not a pipeline stage.** D9 wrote this three months early — *"everything under $0.40 hides the difference between a $0.38 rare and a $0.01 code card, and that difference is what decides later which of them are worth a bulk lot."* Above threshold, a code card lists by the ordinary path. Below it, "PKMNCODES eBay lot" becomes a third sub-threshold disposition beside flat-at-the-floor and flat-price-for-the-run, and `emit` already refuses to write while a disposition is unanswered.

**The own-box convention (owner, 2026-08-23).** Code cards live in their own box, sorted by set. Mixed boxes stay legal (D21), but a pooled card captured into a LOCATED box knowingly consumes a slot number and inflates that box's denominator — the high-water mark counts slots consumed, and a code card consumes one it will never occupy. Convention rather than refusal, because a refusal mid-feed is the rhythm-breaker the capture screen is built to avoid. `docs/CODES-DECISIONS.md` C8 carries the ledger this feeds.

**The render-conditions ruling (owner, 2026-08-23), which is what closes the `views exposure` questions.** Screenshot renders are LOCAL-ONLY: `captures/ui/` is gitignored, the pre-commit hook blocks stray images, and the standing opsec rule already forbids a code-card photo in any listing, README, screenshot or commit. A pooled card's photo appearing in a local render is therefore contained by guards that already exist, and the five advisory questions the `views exposure` row asks are answered by this paragraph rather than by per-screen filtering — which would have cost the owner's own screens their code-card rows. The row stays: it is the tripwire that re-asks the question if a new screen starts rendering stored photos.

**Two opsec triggers fire with this work and must be discharged in the same commit.** `scripts/guard-opsec.sh` has been disabled since 2026-08-03, and D16 says in writing *"Revisit before the codes track handles real cards."* This work makes that condition true. The recorded failure was **over-triggering** — it blocked placeholders in prose about the code format — so the fix is a narrower pattern, never a toggle. And `scripts/views.txt` may never name a URL whose render can contain a code card.

## D25 — The join partitions by game, and `Product Line` becomes a real reader

**The catalog join partitions by game, reading each export's `Product Line` column rather than inferring anything from a filename.** Built 2026-08-23, with the acceptance test this entry implies passed literally: a single-export Pokemon run was captured before the change and re-run after, and every output — join stdout, emit stdout, report, both import files, `decisions.json` — diffed byte-identical. One addition beyond this entry, flagged rather than slipped in: an `--export` file whose `Product Line` cells match no registered game refuses by name, because accepting and silently not using a file is the silent-drop shape the hard rules forbid.

`--export` is repeatable. **Never infer the game from a filename**: read each file's `Product Line` column, map file to games, then invert to game to files, which must be exactly one.

**This corrects a claim this file used to make.** The Deferred entry said the catalog join was *product-line-agnostic*. Measured, it was product-line **blind** — `Product Line` was declared in `CANONICAL_HEADER` and read by nothing, so two exports concatenated would have cross-joined in silence. Blind is not agnostic.

**Catalogs are built per game and never merged.** A merged `_by_number` would report cross-*game* collisions through `colliding_keys` as though they were the cross-*set* collisions that report is actually about — different faults with different remedies, since a set hint fixes one and nothing fixes the other.

`Catalog.from_export` filters to the game's `product_line` and, where set, its `product_line_rarities`, **reports the drop count, and refuses if the filter leaves zero rows** — which means the wrong file, and is the one case where continuing is worse than stopping.

**One import file per game.** Nobody has established whether TCGplayer's Import to Staged accepts a file spanning two `Product Line`s, and `fixtures/staged-import-accepted.csv` proves it for one line only. Per-game files are correct under either answer, so the question does not need settling first.

**Refusals exit 1, write nothing, touch no queue, and never prompt.** Two cases: two files claiming one game, and a game present in the run with no export — the second names up to eight positions and points at the `PUT` correction route. The check runs before any catalog is built, so a run that will refuse costs nothing.

## D26 — A card leaves inventory by a state — `retired` — and a bad photo is replaced in place

Ratifies two items that sat on the Someday list, each marked "needs a decision entry ratified by the owner". Both were named by Gate B's own run.

**`retired` — a terminal card state, `sold`'s sibling.** It was drafted as `removed` and renamed by the owner on 2026-08-23, because the name was already taken: `server/capture_server.py` appends a `removed` HISTORY EVENT when capture-undo hard-deletes a record, T7 asserts no event name is a member of `master.STATES`, and `_state_before_sale` scans history filtering against that tuple — so a state called `removed` would make months-old undo events parse as states and a reversed sale restorable to one. The event keeps its on-disk name (nothing already written moves); the state gets its own word. A card pulled out, damaged, lost or given away has no representation today, so the only options are a sale record that lies or a mid-box delete D10 forbids. `removed` keeps the record, leaves the gap permanent, and carries a reason: `pulled | damaged | lost | given_away`.

**It is not a tombstone in D10's sense**, and the distinction is the reason D10's refusal does not block this. D10 refused to let *undo* invent a third thing the store must explain — not captured, not sold, still occupying a position. `removed` is not that: it is a terminal state on a card that really has left, and `sold` already proved the shape. It also costs less than when it was first written, because D7's amendment has just moved three states off the card, so the `STATES` tuple it joins is narrower than the one it was proposed against.

**Both halves were BUILT on 2026-08-23.** `retired` has its route (`POST /inventory/<box>/<index>/retire`, mark-sold's mirror, reversible with `restores_to`), its four reasons, and an owner-side control on the Inventory screen with a receipt and undo. Re-shoot has its route (`POST /inventory/<box>/<index>/photo` — bytes replaced, sidecar rebuilt from the record, a `reshot` history line carrying both capture ids) **and, since later the same day, its control: on the pull preview, by the owner's ruling** — the screen whose whole job is looking at one stored photo beside its position, so the moment a bad photo is discovered is the moment the remedy is already on screen. A file input rather than a camera (that screen has none; the rig screen is for live shooting), and the screen's look-only header now argues its one write honestly. A sale now refuses a retired card (`card_retired`): the old permissive rule's own justification — "the only way to record a departed card" — is what this entry retired.

**Re-shoot in place, as originally argued.** A bad photograph discovered late has no remedy: D10's undo reaches only the newest capture, and `undo_too_late` currently tells the operator to "correct this card on TCGplayer instead, and leave the position alone" — advice that stops being true the moment this entry exists. The operation is not a delete at all: **replace the photo and sidecar at an existing position, record untouched, position label unchanged, allocator never involved.**

**Two adjacent cases are named here and deliberately left out of scope**, so a later session does not read this entry as having covered them: a returned or cancelled sale (`sold` is terminal and the only reversal is the Fulfiller's twenty-second window), and a single damaged copy among several (D12 hardcodes Near Mint, and `decisions.json`'s unlisted is per-SKU rather than per-copy). D7's fungibility ruling sharpens the second one rather than solving it — a damaged copy is precisely the one copy that is *not* interchangeable.

## D27 — Session state is device-local and may be persisted

**The capture screen's own scratch state may live in `sessionStorage`, because `CLAUDE.md`'s ban on browser storage is about inventory.** D13 puts one truth on the Mac so two devices cannot disagree about where a card is. It was never about the capture screen's scratch state, and reading it that way costs a real thing.

**Box number, set hint, finish claim, rarity claim and the in-flight `capture_id` are device-local and meaningless anywhere else.** They are `useState` today, so a reload loses all of them — and the last one matters most: a reload during a halt makes a lost-response ambiguity permanently unresolvable, and D10's high-water mark hands the burned position straight to the next physical card.

**`sessionStorage`, never `localStorage`**, and the permitted keys are named here so a lint rule can enforce the boundary. Session scope is the point: a new tab is a new session, and nothing about a shift survives closing the browser.

**A second use joined the carve-out on 2026-08-29, and it is a handoff rather than a memory** (D39). `pkmnscan.run-scope` carries a box and the cards ticked in it from `#/inventory` to `#/runs`, because the pipeline moved to a route of its own and the one mass-select in the product did not. It qualifies on this entry's own test — device-local, meaningless anywhere else, not a fact about where a card IS — and it is `sessionStorage` for the same reason everything else here is: a tick list that outlived the browser would be a filter over a spend button that nobody alive remembered setting.

**It differs from the four above in what a reload means.** Those exist so a reload does not lose the shift. This one exists so a reload does not silently WIDEN what the next press pays for, and it is cleared deliberately on three routes rather than expiring: the operator's control, picking a box, and arriving from `#/inventory` with nothing ticked. `app/src/runHandoff.ts` is the one module that reads or writes it.

`useCamera.ts` already argues this carve-out informally for the device id and the rotation chip; this entry generalizes what that file worked out and makes it checkable.

**Trigger mode is explicitly NOT covered.** D19 keeps arming an act, and an armed machine that survives a reload is exactly the automatic-anything that entry refuses.

## D28 — The review answer gets an undo window, and the list stops moving under it

**The review answer gets a twenty-second undo, and the candidate list stops moving between cards.** The review queue's irreversible action had fewer guards than the product's reversible one, which is backwards.

Pressing a digit writes a SKU and a condition onto a real card. `store/queues.py:Queue.upsert` refuses to re-queue a position a human has cleared — deliberately, so an answer outlives the question — so there was no undo, no confirm and no acknowledgement. Meanwhile mark-sold, which is reversible, got a photo to confirm against, a two-step control, a twenty-second undo and a pre-checked `restores_to`.

**That sentence described the owner's screen until 2026-08-30 and now describes the Fulfiller's** (D57). Kept as written because it is the MEASUREMENT this entry was built from, and nothing about the repair depends on it still being current — but a later reader would otherwise go looking for a photo-confirm on `#/inventory` and find none. D57 finished the correction from the other end: this entry gave the irreversible action its undo, and that one took the redundant press off the reversible write, so the sale is one press with `Undo` in the row and on the receipt. `#/fulfillment` keeps all four.

**Two fixes, because there are two halves.**

1. **The list stops moving.** The photo has no reserved dimensions, so answering one card can shift the candidate rows by most of a screen — under a finger already travelling toward a number. Reserve the photo's height and prefetch the next card's image. This removes the cause of most mis-taps and costs no keystroke.
2. **A twenty-second undo**, the shape the product already ships. `Queue.upsert`'s refusal stands for everything outside that window; the window is a hole punched in it on purpose, not a softening of the rule.

**This reopens `docs/DESIGN.md`'s no-acknowledgement rule for this one screen, and the grounds are in the rule itself.** That rule is justified by *undo covers the mistake* — and on this screen undo did not exist, so the rule leaned on something that was not there. Fixing the premise is the honest repair; adding a confirm dialog would have doubled the keystrokes on the screen the owner spends the most hours in, which is what the rule was written to prevent.

**Rejected: requiring a modifier or an Enter to confirm.** Declined for the reason above — one key per card is the property worth keeping.

## D29 — A homogeneous queue may be answered as a group

**A queue whose entries share one reason code and offer one identical candidate may be answered as a group.** Built 2026-08-23, enforced server-side: each entry offers exactly ONE candidate — its own — under one shared reason and one shared condition string.

**A shared SKU is deliberately not required and cannot be what *same single candidate* means**: sixteen cards are sixteen catalog rows, and answering card A with card B's SKU would be corruption wearing a reading. Validate-everything-then-write-everything in one store session (`group_entry_refused` / `group_not_uniform` exit with zero edits); every position gets its own `answered` line tagged `group: N`; the group confirm is the review screen's first solid accent fill, ruled legal because the eligibility conditions are precisely what reduce the state to one action; and the undo reverses per position through the single route, reporting a partial reversal honestly rather than pretending atomicity it does not have.

**This reopens D4's one-card-at-a-time, narrowly, on evidence D4 did not have.** Gate B's queue was 16 of 53, **every one the same reason code**, and detection agreed with itself across every duplicate pair — both Thievuls, both Eiscues, both Pyroars. One systematic fact about the rig's lighting, sixteen identical taps. The discarded pre-rotation run queued 45 with one shared cause.

**Grouping and filtering, always. A group write only under both conditions:** every entry shares a reason code, **and** every entry offers the same single candidate. Anything looser is a bulk write over cards a human has not actually compared, which is what D4 exists to prevent.

D4's digital-only, one-tap choice beside the photo is unchanged for every card that does not meet both conditions — and a group write still shows the photographs it is about to answer for.

## D30 — The physical convention for a gap

**Closed by D58 on 2026-08-30, and not by the marker this entry was waiting for.** The problem below is real and is stated better here than anywhere else in this file — *`Card 17` is the seventeenth slot, not the seventeenth card you can count* — and the answer turned out to be upstream of both halves: a card's number now counts the cards in the box, so selling one makes the card behind it take its number and every label stays countable by hand. There is no gap to put a marker in.

**The digital half stays built and is not deleted.** `neighbors` is still drawn and still worth having for confirming a slot.

**And the sentence about `section_gaps` was false the day it was written — the clause is now deleted outright (owner, 2026-08-30).** This paragraph read that the count "is structurally zero for a consolidated box and `placeSentence` already omits the phrase at zero, so the sentence quietly stops carrying a clause D58 made empty rather than needing a change". It is not zero. `server/capture_server.py:_company` counts the TERMINAL RECORDS between the section's bounds, so a box that has had a sale reports one per departed card — and the server's own comment beside it, *"it answers zero for a box where nothing has left"*, is true and describes the uninteresting case. **Measured on the owner's store: box 1 holds 133 records with 2 sold, so every card in it drew `· 2 slots in this section are empty`** — four times on one screen, since three copy rows and the card band each carry it.

**It had also stopped being TRUE, which is why deleting beats fixing the arithmetic.** Under D58 the box closes up over a departed card, so `Card 19` really is the nineteenth card a hand can count to. The clause's one stated job in this entry — *"the gap count says why the count came out short"* — is void, and a clause telling an operator their count will come up two short now sends them looking for slots the numbering has already absorbed.

**What it cost, measured before it went**: 15px on every copy row in any box that had ever had a sale, and it was the whole reason the line wrapped to three lines rather than one. It is gone from `server.ts:placeParts`, so it reaches no site — not the band, not the copy rows, and not the Fulfiller's card, which renders the joined sentence as visible text. `Place.section_gaps` stays on the wire and on the type, unread, because the field is a fact about the store and this is a ruling about a sentence.

**The physical half is void rather than answered**, which is why the owner never had to choose a marker: the retroactivity problem this entry names — *a convention adopted after fifty gaps exist cannot be applied to them* — is what made a marker unworkable, and it is exactly the problem a rendering does not have. Every existing gap closed the day D58 landed.

**The box audit is easier and still not built.** What is physically in a section and what the record says are the same count again, which is what that check compares.

**The neighbors are ranked rather than joined as of 2026-08-30, which is D41's move one line down.** The owner could not read the sentence this entry specifies: *"it's hard seeing galio and evelynn or between kha and poppy, maybe we make longer (y axis) for them?"*

**The cause is the catalog and not the length.** Every Riftbound name is `Champion, Epithet` — 494 of 1368 carry a comma and none carries two — so the composed sentence holds commas INSIDE names and connectives BETWEEN them, and **the strongest punctuation in the string is the one that is not a boundary**. It fires a median five characters in; the real boundary (`and`) is thirty characters later, so the reader parses grammar to find two proper nouns and then regresses left to recover where the first began.

**So the connectives are deleted rather than restyled, which is exactly what D41 already ruled for the address above it.** `after` and `before` become a muted mono key column, the two names start at one x, the champion carries the ink and the epithet demotes to muted. Finding the second name is a vertical saccade instead of a hunt for a word. `app/src/PlaceNeighbors.tsx` is the renderer and `server.ts:placeParts` is the composer.

**Setting the champions in bold inside the running sentence was the alternative, and it is the move D41 already declined.** It adds a cue on top of the parse instead of deleting the parse: having landed on `Galio`, the reader must still read the grammar to learn which side he is on.

**The keys are the composer's own two words, and that overruled the better-reading pair.** `in front` / `behind` was built first and renders better as a physical pair — and it takes the NEIGHBOR as its subject where `placeParts` takes THIS CARD, so a screen reader would have announced `before Conscription` over a row reading `BEHIND Conscription`. Two true framings of one fact, sixteen pixels apart, is the second-vocabulary drift D22 refuses for reason codes.

**One departure from D41: its payload got size and this one gets position.** Two thirty-character strings cannot take a 44px treatment, and D41's own amendment measured what that costs a list — 44px in the copies row is +86px and drops a copy below the fold.

**The owner kept both sites**, having first said the band's copy was repetitive. Offered the choice with the measurements, they chose to keep the band and the copy rows and restyle both. What that avoids is named here because it was nearly missed: `Inventory.tsx`'s lone-copy branch draws no copies row at all — its own comment puts that at 22% of the store — so a card with no name and no SKU has the band as its ONLY site, and deleting the band would have broken this entry for most of the boxes the owner walks.

**Measured at 1440x900 on box 1 card 19, the owner's own screenshot**: the copy row goes 173.2px to 177.5px, and the neighbor block from two or three lines of 10px uppercase tracked mono to two lines of 12px body. The row is +4px and its height is now CONSTANT, where it used to vary with how long two names happened to be — which is not a fact about the card.

**The Fulfiller is untouched and keeps the joined sentence**, at 20px body through `.card-locations-say`, which `app/tests/fulfillment.spec.ts` floors and D31 keeps unweakened. The firewall is the component graph rather than a selector prefix — `FulfillerCard` does not import the renderer — for the reason `PositionLabel` already records: a prefix is what a refactor drops and an import is not.

**Nothing had ever asserted any of this.** Every Playwright fixture passed `neighbors: null`, which is a real wire state the app draws as no block at all, and the four fixtures that tried to pin the gap count spelled it `gaps_in_section` — **a field that exists in no server, no type and no component** — so they set nothing and the behavior happened to match. Four cases now cover the vocabulary, the split, the single-neighbor end and the deleted clause. Three mutations were observed failing first, and the gap case had to be strengthened to earn its place: asserted against visible text alone it PASSED the re-added clause, because on this screen `said` only ever reaches an `aria-label` — it is the Fulfiller who renders that string as text.

**A hazard found and deliberately not fixed: `PlaceNeighbor.index` is the store key.** `_company` builds it from the allocator index while D58 made every drawn number a count of cards, so on a box with departures the two diverge — box 3 has 9 — and the `#41` a neighbor degrades to when nothing has identified it can name something that is not the slot a hand would count to. It is wrong exactly as it was before this change, and correcting it is a decision about what the server sends rather than about how a screen draws it.

---

The problem as it stood: D10 makes a sold position a permanent gap, and the Fulfiller creates one per order. Nothing has ever told him to leave anything behind in the slot, and nothing teaches anyone to read a position label. Once a section has holes, the slot number and the countable card number stop being the same, and every label in that section becomes uncountable by hand.

**This is retroactive, which is why it wanted settling before more sales happened.** Two halves, and only one was code:

- **Physical**: the operator leaves a marker in the slot a pulled card came out of. Which marker was the owner's call.
- **Digital, and free**: a position renders with its neighbors and its section's gap count — *Card 17, between Mantine and Thievul · 2 slots in this section are empty*. Neighbors make a label countable again without anyone learning the rule, and the gap count says why the count came out short.

**A box audit is the check that closes this loop** — count what is physically in section 2 and compare it to what the record says. Nothing has ever compared a physical box against the record, and D20's `box_fill` and `sections_for` are what make it computable.

---

## D31 — One owner-side view of stored cards, and the Fulfiller does not get a vote on it

**Three routes rendered the same 767 records and the owner named it: they read as separate instances of one thing** (2026-08-23). `#/inventory` searched by SKU and sold a copy, `#/boxes` held the registry and the layout editor with no way into a box's contents at all, and `#/pull` walked a box with photographs. Same store, same records, three looks, and the one question a person actually arrives with — *what is in this box, and can I click it* — was answerable on the screen named after a fulfilment errand and nowhere else.

**All three collapse into `#/inventory`.** `#/boxes` and `#/pull` cease to exist as routes. Box operations — name, sections, seal, delete — live on the box header inside the browse, beside the box they operate on.

**It shipped as two modes behind a switch, and that was wrong.** This entry first read "two ways in, because there are exactly two questions", and it was built that way: a segmented control offering *Browse the boxes* or *Find a card*. The owner, on seeing it:

> *"i imagined moreso in this merge that these wouldn't be two tabs, instead it's basically find a card in a box-based system if anything.."*

That is a better reading of the same merge and it is the one that shipped on 2026-08-23. **The box walk is the SPINE — box → section → card — and finding a card is search over it, not a mode beside it.** The switch is gone. D7's SKU→positions map did not go with it: it is drawn for whichever card the walk currently points at, so "every copy of this card and where each one sits" is a property of the selected card rather than a different screen. Searching narrows the walk and the box strip together; picking a result puts you in the box, at the card, with its copies beneath it.

**Two tabs was the wrong answer for a reason worth keeping**: it preserved the old screens' boundary inside the new route, which is the shape a merge takes when it is performed on the routing table instead of on the question the screens answer. There was only ever one question — *where is this card* — asked from two directions.

**The fold is presentation and never a filter.** Sections collapse (box 2 holds 22 of them over 544 cards), and the collapsed set does not touch what the keyboard walks: arrows, PageUp/PageDown, Home/End and the box strip all still traverse the whole box, and stepping into a shut section opens it. A fold that also filtered would make the arrow keys and the scrollbar disagree about what the box contains, and the operator would have no way to tell which one was lying. Not persisted, for the reason D19 gives about arming: state that acts on its own must be re-established deliberately.

**Collapsed is the resting state, and the control names what ONE press does.** Both were owner reports on 2026-08-23 and they are the same defect seen twice. The screen opened with the selected card's section already open while the button offered `expand all`, so the first press expanded and a second was needed to reach collapsed — *"you gotta click it once or twice for it to be working right"*. The cause was the mark-never-hidden effect firing for the INITIAL, automatic selection, which the operator never made. A move is now a step between two selections, so nothing opens on load, on a reload, or on an upstream write.

The fold control reads `any` rather than `every`, so from a partial state one press always produces the state the label names. Collapse wins the tie because collapsed is where the walk rests.

**A search opens every section holding a match, and clearing it collapses fully.** A result you cannot see is not a result. It is deliberately NOT a clause in `isOpen` — a fold made during a search has to stick, which is the same act-versus-consequence line drawn above. Clearing returns to the resting state rather than restoring what was open before, so there is one state to learn instead of two.

**Mass-select is box-scoped and is not persisted.** The selection clears on a box change because the write it feeds is box-scoped, and a selection surviving into a box it cannot apply to is a loaded gun. It survives a FOLD — the count is carried on the status line and on every section header — because a fold that could hide what a write would reach is the one combination of these two features that is genuinely dangerous.

**The three routes that had no client half at all landed here, on this screen** — the whole-box delete, the mid-box delete with its contiguous shift, and the retroactive claim corrections at both the card and the selection level. They existed with full T7 coverage and no control anywhere, which is what produced `CLAUDE.md`'s route-is-not-a-feature rule; this is where they became reachable, and `app/tests/inventory.spec.ts` is what asserts they stay that way.

**The re-shoot control comes with it and may not be dropped in the move.** D26 put it on the pull preview deliberately — *"the screen whose whole job is looking at one stored photo beside its position, so the moment a bad photo is discovered is the moment the remedy is already on screen"*. That argument is about a detail panel showing one card's photograph, not about a URL, so it transfers intact to the browse's card detail. A merge that loses it has broken D26.

**`CLAUDE.md`'s "six screens and six routes" was already wrong before this entry and is rewritten by it.** The table in `app/src/App.tsx` carried SEVEN — the gallery makes the seventh, and that file's own comment says "it matters more at seven routes than it did at three" while `CLAUDE.md` still said six. Five remained: capture, review, inventory, fulfillment, gallery.

**It is SEVEN as of 2026-08-30: `#/runs` (D39) and `#/pricing` (D49).** Recorded here because this is the entry that owns the count and because the direction matters: this merge deleted two routes that rendered one thing, and that ruling is untouched by routes being added for things no route rendered at all. `#/inventory` still holds the walk, the card, its copies and the box's operations; what left it is the pipeline, which was never one of the three screens this entry merged, and what joined it is hand-pricing, which no screen has ever offered. The count is restated in `CLAUDE.md`, `docs/map.py`, `README.md`, `app/src/App.tsx` and `scripts/views.txt`, and the not-rendered-rather-than-hidden rule for the Fulfiller's nav is untouched — it was never about how many owner routes there are.

**And the count was false in five places for the whole of D39's LIFE, WHICH IS THE FINDING WORTH MORE THAN THE NUMBER.** `#/runs` landed and `README.md` went on saying five screens, `docs/map.py` five routes, and `app/src/App.tsx`'s own header — the file that HOLDS the table — `Five now`. None of it failed a check, because `scripts/docs-audit.py` reconciles no count of anything: D18 deleted the last published one deliberately, on the argument that a verifiable fact nobody can disagree with is not load-bearing prose.

That argument is right about a number in a report and wrong here, and the difference is worth naming. A count of routes is what a session reads to learn the SHAPE of the product before it edits anything, and a wrong one sends it looking for a screen that does not exist or building one that does. It is still not mechanically checked — a check would have to decide what counts as a screen, and this entry is not opening that — so the defense is that this paragraph exists and that D31 is named in every file that restates the number.

**The Fulfiller's surface is downstream and is not a counterpoint.** Recorded because it was argued the wrong way round and the owner corrected it: *"do not concern yourself with fulfiller concerns, fulfiller concerns/settings are downstream of build work and should not be a counterpoint to any build work."* The case was real — `#/pull` was offered as a screen the fulfilment flow leans on, as a reason to merge less — and it is exactly the inversion this rule forbids. D5 makes the Fulfiller's screens a *skin* over what the owner's build produces and D13 puts one truth behind both; a skin settles after the thing it presents exists. Letting it veto upstream structure lets a consumer decide the shape of what it consumes.

**What this does NOT license, stated because the sentence above is the kind that gets overread**: `app/tests/fulfillment.spec.ts` and `docs/DESIGN.md`'s nine hard constraints still pass, unchanged and unweakened. `#/fulfillment` is not merged into anything and keeps its own route — it is a different persona at a different posture, and it is the one screen in the product whose whole design is a floor. The ruling is about which arguments may decide architecture, not about which tests may go red.

---

## D32 — The pixel budget is spent on the card, not the desk

**Identification crops to the detected card in memory, behind `--crop`, and the crop and the max edge are chosen as one pair.** The owner asked, 2026-08-23, whether a mass crop or a per-run trim would cut token load. The instinct and the axis were both right: measured over 544 real frames, the card fills 80–88% of the width and only 61–72% of the height, so the waste really is top and bottom.

**Detection, not sliders.** `geometry.detect_card` already answers this per frame, locally, for free. Over all 544 box-2 frames it found the card **544 times, refusing none** — 467 by edge search, 77 by tone. A fixed percentage would be a guess that is wrong per frame, because card area across that box ranges 39% to 81% as cards move on the tray. The detector knows; the operator would be estimating.

**At identify time, in memory, never on disk.** The photograph is not modified. A wrong crop costs one re-run of a free local step; a crop written at capture is irreversible by the time anyone notices, because the card is back in the box — D10's undo argument read the other way, since undo is safe *because* the card is still in your hand and at identify time it is not. It also means the 682 photographs already taken benefit, which a capture-time preset never could, and that every other consumer keeps the full frame: the review queue photo a human judges foil against, the pull preview matched to a physical slot, the re-shoot comparison.

**A refusal sends the whole frame.** `detect_card` answers `None` rather than guessing (T6: *not found must be a refusal, never a guess*), and the honest response is to send what was always sent. The preflight names the count, because a nonzero refusal count means some cards are going at whole-frame cost.

### The cost model was got wrong in public first

The first estimate reasoned from the card's AREA in the frame — 53%, therefore a ~40% saving. That is wrong, because `MAX_EDGE` normalizes the LONG EDGE rather than the area. The frames are 2160x3840 (aspect 0.56) and a card is aspect 0.72 — fatter — so at an unchanged 1568 cap the crop sends *more* pixels: measured, **+26% cost**. Cropping buys resolution by default and only buys money if `--max-edge` comes down with it. Recorded because the arithmetic looks obvious in the wrong direction and a later session will re-derive it the same way.

The measured frontier, 20 real frames, against a full-frame @1568 baseline of $0.72 for box 2 and 268x57 native pixels on the collector-number strip:

| config | box 2 | native px on the number | vs today |
|---|---|---|---|
| crop @1400 | $0.76 | 1.95x area | dearer, much sharper |
| crop @1200 | $0.62 | +16% linear | cheaper AND sharper |
| crop @1100 | $0.56 | +6% linear | cheaper, ~parity |
| crop @1000 | $0.50 | -3% linear | cheaper, ~parity |
| crop @900 | $0.44 | -13% linear | cheapest, softer |

**Off by default, behind `--crop`.** It changes the bytes a card is read from, and Gate B's 53-card end-to-end run — the only one this project has — was full-frame.

**Known gap, named rather than patched: the crop is not part of the cache identity.** The cache is keyed by card key plus the profile's prompt fingerprint, and neither `--crop` nor `--max-edge` is in that hash — so a cropped run over cards already answered uncropped would reuse the old answers and report cache hits. It cannot bite today: box 2 has zero cached answers, and the A/B that measures this ran in isolated `PKMNSCAN_HOME` directories precisely so the two configurations could not read each other's cache. The remedy when it matters is the shape `rarity_fingerprint` already established — a sibling hash kept deliberately OUT of `prompt_fingerprint`, so recording what an image was read from cannot move `1ef974bf511d`.

### The screen offers the pair, not the two controls

The owner, 2026-08-25, asked to be walked through how they were supposed to understand crop from the dialog they had. They could not. The run panel drew a checkbox reading `Crop to the card` beside a number reading `Max edge`, and those two labels were **every user-visible string in the block** — while everything above lived in this entry and in a code comment.

**The paragraph on getting the cost model wrong is what makes this a defect rather than a missing sentence.** A checkbox that reads as *send less* beside an unexplained number is an invitation to do exactly that, and the panel had no guard: it was one click from the most expensive setting on the frontier while appearing to ask for the cheapest.

So `READINGS` offers three named PAIRS, and a pair cannot be got wrong. `Measured best · 1200`, `Cheapest · 900`, `Whole frame · 1568` — three rows of the table above, each setting both values, each carrying the sentence that says what it costs and what it buys. `Sharpest · 1400` is not one of the three: it is the row strictly dearer than the baseline, and three chips fit the 340px end of D38's column where four do not. It lives behind **`Custom`**, which reveals the old checkbox and number unchanged — demoted, never taken away, because a free-form max edge is a real need and this frontier runs wider than three points. **The warning follows the mistake to where it is still reachable**: `Custom`'s sentence is the only one naming the +26%, because `Custom` is the only state that can produce it.

**The estimate is void when the reading moves**, and that was a hole in D33's money gate rather than a copy gap. `RunPanel.tsx`'s `scopeKey` was `box:indices` alone, so unticking the crop after Check cost left a stale figure above a live *Spend $0.62 and identify 36 cards* button. The effect's own comment already stated the rule — *a confirm whose first step described a different set of cards is not a confirm at all* — but it named cards where the estimate is computed from BYTES, which the crop and the max edge decide. Both values are in the key now. `app/tests/run-panel.spec.ts` asserts the void as an ABSENCE, the same shape as the spend button's own case, observed failing against the old key first.

**The cache gap is now said on screen, in the words it means.** Where the preflight reports any cache hits, the quote carries one line: cards already answered keep the answer they were first read with, and the reading only reaches the cards being sent. No hash is named — the panel has no business publishing `prompt_fingerprint` — and nothing about the gap is closed. Drawn only above zero, because a warning about answers that do not exist is one an operator learns to skip.

### The reading is drawn, not only described

Built 2026-08-29 at the owner's instruction: there should be a crop preview on the runs tab, given that the crop is selected there. `POST /pipeline/crop-preview` is free, writes nothing, shells out to nothing, and answers what the selected pair would send for one card; `RunPanel.tsx` draws it in a column beside the chips.

**The measurement that decided the design: the rectangle is IDENTICAL at 1200 and at 900.** The cut comes from `detect_card` plus the aspect correction plus `CROP_PAD`, and not one of those reads `max_edge` — the downscale happens after. So a preview drawing only the crop would leave two of the three chips looking exactly alike, which is most of the question the owner was asking. The pair has two axes and one picture cannot carry both:

- **The crop decides FRAMING**, shown as a composite: the discarded margin is the stored photograph at 35% opacity, and the cut region is **the payload itself**, at full strength, with the accent outline on the boundary. It answers *is the collector number inside the bytes* — box 2's failure, 38 numbers cut clean off — and **a picture of the crop alone could never answer it, because what was cut is not in the crop.**
- **The max edge decides RESOLUTION**, shown by a **1:1 window onto the same file**. `background-size: auto` with a pixel `background-position` IS 1:1, with no scaling arithmetic to get wrong and no second request. That is the review queue's loupe aimed at the PAYLOAD rather than at the stored photograph, and the same standards are behind it: FADGI and Metamorfoze both require this class of judgement at 100%, and here a downscale is precisely what is being judged.

**The frame drew the stored photograph until the owner caught it** — the preview should show the depixelation as the options change. It did not, and could not: it was `GET /photo`, the same bytes at every reading, so the one thing being changed was the one thing the picture could not show. It draws the prepared bytes now, which costs 235-441KB on a localhost socket, debounced, for one card.

**And the frame still cannot show the difference, which is physics rather than a defect.** It draws the payload at roughly 28% of its pixels, and no two downscales are distinguishable under a reduction that large — an operator comparing 1200 against 900 will correctly see no difference and wrongly conclude there is none. So the caption says `shown reduced`, and the 1:1 window below is where the comparison is made. Recorded because the obvious fix is to enlarge the frame, and no size short of 100% would work.

**The band stopped being a second image, and that is what makes the pair trustworthy.** It was a separately encoded JPEG of the number strip; it is a RECTANGLE INTO the sent bytes now, and the window paints that region of the file the frame is already showing. One image over the wire, two views of it, and **the second cannot drift from the first because there is no second file to drift**. It also costs fewer bytes than the two-image version it replaces.

**The window follows the pointer, and that is what makes a bandless game usable.** It rests on the collector number where the registry claims one and reads whatever the pointer is over otherwise — so on Riftbound, where nobody has measured where the identifier prints, the operator points at it themselves. A refusal that had taken the magnifier away with it would have left that game strictly worse off than before the preview existed.

**One computation, two callers, and that is the honesty of it.** `identify/images.py:crop_rect` is the rectangle `card_crop` cuts, extracted so the screen can draw it rather than derive one of its own. A preview with its own copy of that arithmetic can reassure the operator about a crop it is not describing — EXACTLY the failure the aspect correction was written for. `card_rect` splits out beside it, unpadded, because the number band is a fraction of the cardboard rather than of the cut. T6 asserts the identity and was observed failing against a `card_crop` that had quietly stopped using it; the extraction was checked byte-for-byte against the committed version on 25 real box-2 frames.

**It is pressed before the preflight, which is the order of the decision.** The reading is chosen, the estimate is what the choice costs, and the spend button does not exist until the estimate has answered — three steps down the panel in the order they happen. It is keyed on the same `scopeKey` that voids the estimate, so a chip press redraws the picture and clears the number together. The previous strip stays up, dimmed, while the next is fetched: blanking would move `Check cost` under a pointer already travelling toward it, which is D28's hazard on the one panel whose next button spends money.

**`rect: null` means two opposite things and `method` is what separates them.** The crop being off is a setting the operator chose; detection refusing is a card going at whole-frame cost when they asked for a crop. The route reports both and the strip says which, because the preflight counts refusals across the box and this is where one can be looked at.

**One card, beside the chips, walked by the arrow keys — and it was three abreast for a few hours.** The first build sampled three cards evenly across the box on this entry's own measurement that card area runs 39-81%, so the front of a box does not stand for it. That argument is right about SAMPLING and it lost to a plainer fact, which the owner put plainly: the preview was too small. Three pictures across a panel are three small pictures — each frame drew 112px wide — and a preview nobody can read is not a preview. One card in a column is ~2.5x the linear size for the same block of screen, and the spread is reached by WALKING, which is also the only version that lets the operator look at a card they actually suspect.

**The walk wraps, on both sides of the wire.** The route takes `offset % total` so a stale client cannot send a negative, and the screen wraps too so the caption stays inside the box. Arrow keys are the control and the buttons beside the card do the same thing: a key with no visible affordance is a key nobody finds. **The listener is guarded on the event's target** — this panel holds a number input and a `decisions.json` textarea, and an unguarded window listener steals the caret keys from both. The fetch is debounced at 140ms, because a held arrow key repeats faster than a photograph decodes. Measured at ~115ms a card — 63-84ms of detection, ~51ms to crop, downscale and encode — so firing on every chip press and every arrow press is affordable.

**Two things came with it that are not about pixels.** `make server` ran bare `python3`, whose interpreter has no Pillow, so this route would have refused on the one machine it is for; it runs `$(PYTHON)` now, which is the venv where one exists and `python3` where none does — the property that line protected was *must not NEED `make venv`*, and that is intact. And the imports are inside the handler, so a missing Pillow is a named `imaging_unavailable` refusal rather than a server that will not boot over a preview nobody asked for.

**D24's tripwire fired, and it is answered by D24 rather than by new machinery.** `scripts/docs-audit.py`'s `views exposure` row now names `#/runs` as a screen that can draw stored capture photos — exactly what that row is for — and the render-conditions ruling already answers it: renders are local-only, `captures/ui/` is gitignored, and the pre-commit hook blocks stray images. No per-screen filtering.

**What this does NOT do: it does not record what a PAST run sent.** The strip recomputes with today's detector, so it describes the run you are about to start and nothing else. That matters for box 2 specifically — its crops were cut by the flat pad this entry records, fixed in `d431afb` about 35 minutes after that run was submitted, so a recomputation shows the corrected crop rather than the one that lost 38 collector numbers. Making a run replayable means recording the box on the run payload at identify time, which is a change to what `identify` writes and has not been argued. Until it is, this is a preview and never a receipt.

**The band is the registry's to grant, per card, and this shipped wrong first.** The first build cut `geometry/crop.py`'s number band over every card whatever game it was, and `pipeline/games.py` refuses exactly that in writing: the bands are fractions measured on a Pokemon card, and a band claimed without that measurement is cut over the wrong pixels. Box 1 is Riftbound, the owner opened it, and the strip drew that card's RULES TEXT as though it were a collector number. Only `pokemon` claims a number band today; a game that does not gets **no band and the registry's own sentence saying why**, the same refusal `crop_regions` makes reached through the same field. **The CUT is unaffected** — a card is 63x88mm whatever is printed on it — and that asymmetry is why the two halves are separate answers.

Worth naming as a class: the registry already held the answer and the first build did not ask it. A preview is a second reader of everything the pipeline knows, and every fact it draws has an owner somewhere in `pipeline/` — drawing one from a constant instead of from its owner is how a picture ends up more confident than the thing it depicts.

**What would reopen this: a refusal the walk never reaches.** The preflight counts detection refusals across the whole box and the walk shows one card at a time, so a box with three refusals among 543 is a hunt. If that costs a real session, the fix is a control that jumps to the next refused card once the preflight has answered — not a return to sampling, which is what made the picture too small to read.

---

## D33 — The pipeline is reachable from a screen, and one route can spend

**The four pipeline commands are reachable from a screen, and exactly one route can spend money.** Built 2026-08-24, and it is the largest instance of `CLAUDE.md`'s route-is-not-a-feature rule this repo has had. The owner asked how to push runs at box or section level from the app, get data back and manage CSVs — and then, after a session that designed the screen, interviewed them about it and drew a mockup without building any of it, asked why none of the promised UI existed. Both were correct. `./pkmnscan identify | join | emit | reconcile` has existed since build-order step 4, has been through a 53-card run and a 544-card run, and could be reached only by somebody typing at a terminal.

**`server/pipeline_routes.py` is its own module because it is the one part of the server that can cause money to be spent.** `server/capture_server.py`'s header promised that this process never spends money: it holds no API key and makes no outbound call. Both halves stay literally true — nothing there reads a key or opens a socket to Anthropic — and the sentence was written to mean more than its letter, so it is rewritten rather than leaned on. A promise that quietly narrows to a technicality is the drift D16 exists to catch.

What replaces it, because a guarantee deleted and not replaced is a regression:

- **One route spends and is named for it** — `POST /pipeline/identify`. It refuses without an explicit `confirm` field, and it refuses a second run over a capture directory a live run is already reading: a double-click is the realistic accident, and two live batches over one box is two invoices for one answer.
- **The preflight is free, is a separate route, and creates no run directory at all** — `identify --dry-run` returns before `runs.create`. It is what the screen must show first.
- **Everything else is free and re-runnable**, which is the property D1 gave the two-phase split.

**The money step spawns and is never awaited; every other step runs in the request.** Not a preference — the shape of the work. A Batch takes minutes to hours and no HTTP request may be held open for that; `join`, `emit` and `reconcile` are local arithmetic over a parsed CSV. The child is detached and logs into the run directory, so **a run outlives the server that started it**: the Mac sleeps, `make server` restarts, a tab closes, and the poll still reads the run directory. `cli/runs.py` already makes a run an immutable input rather than state, and this leans on that entirely — nothing is held between requests.

**Scope is a box, or a selection inside one.** A subset becomes a directory of symlinks built **outside `captures/cards/`**, which is load-bearing: `identify.sidecar.scan` walks its root recursively, so a scope directory under it would be walked by the next run pointed at the box above and every card submitted twice. Gitignored under the opsec rule as well as the derived one — a bearer instrument reached through a symlink is still a bearer instrument.

**Exports are uploaded, never named by path.** A screen cannot know what is on the server's disk, and a route that opened any absolute path a request named would be a file-read primitive guarded by an origin header. It also leaves the run holding the exact bytes it was joined against, which the manifest could only describe by hash.

**The money gate is two steps and no typing** (the owner's ruling). Check cost, read the count and the estimate the command itself printed, then press the confirm that appears beneath them. The confirm **does not exist** before the preflight has answered — absent, not disabled, because a disabled button is one attribute away from pressable and that attribute is what a later refactor drops without noticing. `docs/DESIGN.md` permits a gate on a genuinely destructive action; the cheapest honest gate here is making the number impossible not to have seen.

### Placement, and where that argument went

**The panel sat on `#/inventory` until 2026-08-29 and now has a route — see D39**, which is where that argument was overruled and how. The reasoning here is unchanged and is what D39 was built against: D31 collapsed three screens into that route on the finding that they were separate instances of one thing, and a run is not a different thing again — it is something done to the box being walked, or to the cards just ticked in it. A route of its own would re-implement the box strip, the search and the mass-select, and would then be free to disagree with them about what is selected.

**What D39 does with that is split it.** The box IS re-answered, by a picker of its own, which is cheap and cannot disagree with anything. The SELECTION is not: `#/inventory` keeps the one mass-select in the product and hands the ticked indices over, so there is still exactly one place a selection can be made. Read the paragraph above as the specification that build had to satisfy rather than as a placement this file still asserts.

**It is no longer folded, and neither is `BoxOps`** (the owner, 2026-08-24). This entry read *folded by default*, on `BoxOps`' measured reason: ~250px, reached once a box, on a screen whose question is *where is this card*. The owner overruled it in three messages, the last unambiguous: both box and run, no click-in functionality, the buttons just there.

The argument the fold rested on has the weaker half of a true premise. Reached once a box IS every box, which is the definition of the primary task rather than an exception to it, and NN/g prices a collapsed panel at five accumulating substeps — scroll, scan, decide, target, wait — before the first click of real work. This repo's own record already made the same point one notch further along: three routes shipped with full T7 coverage and no reachable control at all, which is where the route-is-not-a-feature rule came from. A control behind a fold is one step better than that, not a different kind of thing.

**What replaces the fold's saving has been rewritten three times, and the third is the panel's own MEASURE** (2026-08-26). The column is gone: its HEIGHT was setting the grid row that positioned the card's copies (D38, amended), so the panel moved to the last row of the content column and got the full width instead. Given 1024px it draws **625px closed and 1143px open**, against 799 and 1461 in a 370px track, with no code change — the head stops wrapping four command names and the step notes and free steps unwrap with it. Nothing folds, nothing is capped, nothing scrolls internally, and every control this entry protects is still drawn unconditionally; what moved is reading order. `app/tests/run-panel.spec.ts` now asserts that as an absence — `<details>` and `<summary>` at zero inside the panel — which is the one form of this ruling no future relocation can falsify.

The two earlier answers, kept because the sequence is the argument. **What replaces the fold's saving is the COLUMN, not the disclosure** — and that sentence said *the row* until 2026-08-25, which is the honest way to record what actually happened. `BoxOps` and the run panel first shared one grid row beneath the card detail (`.browse-boxrun`, `1fr 1fr`), so the pair cost one panel's height rather than two. `defaultOpen`, the two disclosure triangles, their `[open]` flips and both `-webkit` marker resets were deleted then and stay deleted. **They then stood in a third column of their own, to the right of the card** (the owner, the next day). It is the same argument at its limit rather than a different one: the row cost the card's column one panel's height, and the column costs it nothing. The space came from the card's own photograph, shrunk to the height of the fact rows beside it — see D38. Stacked in that column `BoxOps` sits above the run panel, and `.browse-boxrun` is a flex column rather than a grid so the shelves that get no box panel produce no leading gap.

### All four steps are on screen in every state

**And three of them were not until 2026-08-25.** `RunPanel.tsx`'s `STEPS` list is authored rather than derived from `phase`, and says why in its own comment: a screen that only drew the current step would leave the operator unable to see that emit exists until join had finished. That promise was kept against `phase` and broken against `detail` — join, emit and reconcile rendered inside the open-run guard, so with no run picked the panel drew Identify and nothing else, and **with no runs at all the pipeline's other three quarters existed nowhere in the document**. A first-time operator could not learn the pipeline had four parts until after they had paid for one. `app/tests/run-panel.spec.ts` demonstrated the gap in its own body: it had to click a run row before it could assert the four titles.

The heads and the notes now always draw; the CONTROLS stay behind a picked run, **absent rather than disabled** — the discipline the money gate already keeps, for the reason `.run-button`'s comment gives. One sentence above the three says which state you are in.

**Three defects were fixed alongside, all reachable before and none cosmetic.** `stepOut`, `decisions` and `decisionsBad` were never cleared when the open run changed — so run A's answer rendered under run B, and `saveDecisions` posts the textarea to whatever `openRun` is at the moment of the press, which could write A's edited `decisions.json` into B. A step's answer now renders inside the step that produced it and is matched on **the step the click requested, never the server's echo**; the spec mocks all three routes and returns `step: 'join'` for every one, which was harmless only while the answer rendered unconditionally. And the run list is re-read on a timer — 4s while anything is live, 20s otherwise — because a run started in a TERMINAL begins live, so a poll gated on *something is live* could never discover the one case this route exists for. A live run says how long it has been running, from its own `created_at`: `identify/batch.py` logs only when the batch's status CHANGES, so a console tail written forty minutes ago is indistinguishable from a hang. Elapsed is measured, not estimated — there is no per-card signal on the wire and **no progress bar is invented**.

**Every command's stdout is shown verbatim and nothing summarizes one**, which is `docs/DESIGN.md`'s copy rule for the owner's screens. The one thing the panel adds on top is the download link for a file the console can only name — the gap `docs/GATES.md` records as what Gate B did not close: emit's import files existed only as filenames in terminal output the owner never sees when someone else drives the commands.

**`decisions.json` is edited as text, not as a form.** The route says in its own comment that it does not validate what a disposition MEANS — `emit` owns that refusal — and a typed form would encode the schema a second time in TypeScript, where nothing audits it against `pipeline/decisions.py`. The file already explains itself: `join` writes a `_note` block naming every field and what `emit` will refuse without.

**`--force-resubmit` is deliberately not offered to a screen.** It is the one identify flag whose purpose is to pay again for an answer already bought, and D32's known cache gap means a re-crop cannot be distinguished from a re-run by the cache. It stays a terminal flag until the crop is part of the cache identity.

---

## D34 — A listing hold is released against the releasing box's own copies

**A box's listing holds can be released on the operator's word, budgeted by that box's own unsold copies.** Built 2026-08-24, and it was found by a box that could not be deleted. The owner asked why box 1 — the 53 Gate B cards — refused `box_not_empty_of_commitments` when nothing in it had been sold or retired. It was held by 45 listing records carrying **53 staged copies and one live**, written by run `2026-08-22-box1-03`, whose `reconcile.txt` records a real Export From Staged confirming the import had landed on TCGplayer. The rows had long since been cleared there. The store had no way to know that, and no way to be told.

**The gate had two grounds and one door.** A box held open by a sold or retired card can be freed: both states reverse on their own routes, and the refusal names them. A box held open by a LISTING could not be, ever. `staged` is written by `reconcile` and drawn down in exactly one place — `cli/cmd_join.py`, by the **rise** in live quantity a fresh Filtered Export reports. That is the right answer for an import that lands: the copies move to live and the staged count follows them down. It has no answer at all for an import that does not. A staged row deleted on TCGplayer never becomes live, so live never rises, so the drawdown never runs. The count stands forever and the box is permanently undeletable.

`store/master.py:staged_stale` has named exactly this case since D7's amendment — its own docstring calls it *the import nobody finished* — and until now **nothing anywhere could act on the warning**. A diagnostic with no remedy is the shape of this defect.

**The release is budgeted by the calling box's unsold copies. It never zeroes a SKU outright, and this is the owner's ruling of 2026-08-24 overruling the first build.** That build zeroed the record, on the argument that *TCGplayer holds nothing for this SKU* is a claim about TCGplayer and therefore cannot be scoped to a box. The owner overruled it, and the replacement reason is better than the argument it replaced:

> **A release reached from box 1 must never be able to give up commitments that only box 3's copies could account for.**

A budget makes that impossible structurally rather than unlikely by care. Each SKU gives up at most the number of unsold copies the calling box holds; `pipeline` and `store` are untouched by the distinction because `Listing.release(budget)` is where it lives.

**The remainder is deliberate, and confirmed by the owner.** Where a SKU is shared, what is left keeps `_listing_hold` non-empty, so **the box stays refused after a release that did exactly what it said**. That is the honest state — TCGplayer really is still holding copies of a SKU this box has copies of, and D7 makes every copy equally a candidate for being one of them. It is not a failure of the route, and the screen's job is to say so before the press rather than let it read as a broken gate.

**Least-committed first: `pushed`, then `staged`, then `live`, against one shared budget.** Not `budget` from each stage — two departing cards cannot account for two staged *and* two live copies, and per-stage decrements would give up four commitments for two cards. Which stage a given copy actually backs is unknowable by construction (D7: the backing is deliberately unrecorded), so the order is a rule rather than a lookup, and it is the conservative one: `pushed` is a row in a file that may never have been imported, `staged` is a row TCGplayer confirmed, `live` is a card actually for sale. Being wrong about `live` costs the most, so it is surrendered last.

**A sold or retired copy does not count toward the budget.** It has already left — a sale decrements `live` where it can — and it is not one of the copies a remaining commitment could be backed by. It is also what the operator counts when they look in the box, which is the number they will check the screen against. Such a box is refused by the sold clause anyway, so this opens no new dead end.

**`staged_at` clears only where `staged` reaches zero.** `Listing.set` stamps it as `staged_at or at`, so a record released to zero and later re-staged would otherwise carry the old date forward and read as stale on the day it was staged — a warning firing on success. A record with copies REMAINING keeps its stamp, because those copies really have been staged since that date and are exactly what the warning exists to find.

**The record survives at zeros rather than being popped**, because `_listing_hold` already reads all-zeros as not held.

**It asserts rather than measures, and that decides the rest.** D8 and D11 put the authority over these numbers in the export, and **no export this pipeline reads can say *nothing is staged***: a Filtered Export reports live quantity, and an Export From Staged lists the rows that *are* there, so absence from it is unbounded — a SKU can be missing because it was never staged. The only party who can state that TCGplayer holds nothing is the operator looking at TCGplayer. A route whose entire content is a human's claim owes three things:

- **`confirm: true`, required.** D33's field one register down. That route refuses without it because the next thing that happens costs money; this one refuses because the next thing that happens is a fact being recorded on somebody's word.
- **A history line, always.** `listings_released`, box-level like `box_deleted`, carrying the box, the SKU count, the copies given up **and `still_held`**. The last is the half a later reader cannot re-derive: without it the log would say a release happened and not that it was partial. After the write there is no other evidence the counts ever stood.
- **The plan, ahead of the press.** `GET /boxes/<box>/listings` — free, read-only, creating nothing.

**Two routes, and the free one comes first — D33's preflight shape, and the owner asked for it by name.** The first build reported the blast radius in the *receipt*: honest, and after the write. An operator releasing from box 1's header learned box 3 was involved once it was already done. The preflight names every SKU, its copy count, what it would give up, what it would keep, which other boxes hold copies, and **`frees_box`** — whether the box would actually become deletable. `server/capture_server.py:_release_plan` is the single source for both routes, and it simulates by copying the record and calling `Listing.release` itself, so the preview cannot drift from the write even if the ordering rule changes.

**The screen fetches the plan on opening the panel, and the control that releases does not exist until it has answered** — absent, not disabled, `docs/DESIGN.md`'s rule for the run panel's spend button applied for the same reason. No extra press: the fetch runs on open.

**It reaches no other ground of the refusal.** A sold or retired card still holds its box open after every listing in it is released, because those are departures recorded in the store and this route says nothing about a departure. T7 asserts the refusal survives.

**One press on the screen, where the whole-box delete takes two.** That delete used to demand the box number TYPED, on the grounds that its risk is destroying box 9 while looking at box 95 and a gesture that cannot be performed by momentum answers that; the owner traded the typing for a second naming press on 2026-08-26 (D20, amended). The contrast survives and is smaller: this control's risk is a claim that turns out to be wrong, and neither typing digits nor pressing twice makes anyone go and look at TCGplayer. The plan above the button is the gate here — numbers a person can actually check. Nothing is destroyed either way: a wrongly released count is re-established by staging again.

**Each press is its own assertion, and the cap is per press.** Releasing twice spends the budget twice; the route keeps no memory of what a box has released before. That follows from the budget being a statement about the copies in front of you rather than a quota.

**`GET /boxes` now reports `retired` and `listed` beside `sold`.** Counted in the walk `_box_row` was already running. Without them a screen could say a box has commitments and never which kind, and the three kinds have three different remedies — so the delete panel recited the rule and the operator learned which clause applied by pressing an irreversible button and reading the error.

**What would reopen this: a staged quantity the pipeline can read.** If `reconcile` were ever pointed at a *fresh* Export From Staged and allowed to set `staged` absolutely — absence meaning zero — the release would stop being the only way to clear a stale count, and the honest thing would be to prefer the measurement over the claim. That is a change to `cli/cmd_reconcile.py`'s contract (it currently moves `pushed → staged` and reads no absence), not a change to this entry, and it has not been argued.

---

## D35 — A number that cannot be read falls back to the name, and the card still faces a human

**Built 2026-08-24, and it was found by the owner asking why the review queue was full of cards they did not think needed reviewing.** It held 46 entries, every one `no_catalog_row`, every one with **zero candidate rows** — so they could not be answered at all, only skipped: `POST /review/<box>/<index>/answer` refuses an entry with no candidates as `no_candidates`.

**The gap was one line, and its comment stated the false assumption outright.** `pipeline/join.py`'s Pokemon lookup fell back, when a card carried no number, to `catalog.rows_for_blank_number_name` — an index of **only those export rows whose own `Number` cell is blank**. Its comment: *"No collector number on the product (code cards, some promos). These are exactly the rows whose `Number` is blank."* That reads `card.number is None` as a fact about the PRODUCT when it is a fact about the READ. The two coincide only while the photograph is good.

Box 2's 544 cards were cropped by a pad that cut the collector number off the bottom of the frame (fixed in `d431afb`, ~35 minutes after that run was submitted). 37 came back with no number at all and 9 with a **National Pokedex number read off the artwork strip** — `0326`, `0342`, `0934`, `721`. Every one landed on that fallback, found nothing, and queued as `no_catalog_row` against an export that held its row the whole time and had already matched that row for other copies in the same run.

**Measured against that run's own export, matching by name inside the declared set: 47 cards carried an unusable number (38 blank, 9 Pokedex-style misreads); ONE of them — `2/7`, `Stonjourner` — has since been deleted from the box, so 46 reach the rung and 45 OF THE 46 RESOLVE TO EXACTLY ONE CARD, WITH ZERO AMBIGUOUS.** The one that does not is a Mega Signal misread as `Mewtwo ex 009/102` — name and number both wrong, so nothing can rescue it, and it correctly stays `no_catalog_row`.

**Those are the counts on disk today, and the arithmetic was re-checked on 2026-08-25 rather than carried forward.** This entry was written before D36's realign existed and read "46 of the 47"; the deleted card was still being counted. `inventory/parked.json` holds 45 `number_unread_name_matched` entries and `inventory/review.json` the single zero-candidate `no_catalog_row` — which is the run this paragraph is about, as it actually stands.

**The name is the more reliable field, which is the argument for the whole rung.** T1's recorded misses are `051/197` for `031/197` and `271/167` for `211/167` — confident answers, **name right, digits wrong**. `docs/GATES.md` says no confidence threshold fires on those. The same shape produced all nine of box 2's wrong numbers. A rung that trusts the name when the number finds nothing is not a weaker check; it is the check aimed at the field that survives.

**It fires only on an empty result, and both emptiness cases count.** A number that matches rows is never second-guessed. What was nearly missed is the second case: four of box 2's misreads carried a denominator too, so they composed a well-formed key that matched nothing and stopped there — so an empty NUMBER lookup falls through as well as a missing one. It cannot mislist anything, because it is reached only when the card was bound for `no_catalog_row` regardless, and what it produces is a queue entry rather than a listing.

**`CLAUDE.md`'s HARD RULE IS NARROWED, NOT REPEALED**, and this paragraph is the narrowing. That file says *"Never join on Product Name — it inconsistently embeds numbers."* It is right, and the inconsistency is live in the owner's own data: box 2's export writes `Delibird - 105/132` and `Nickit` in the same column, and the first pass at the measurement above matched raw names and scored 35 of 46 instead of 46 of 47. So: **never as the primary key; permitted as a last resort that fires only when the number key finds nothing; folded on both sides by `join.name_index_key`, which strips a trailing ` - <n>/<total>` and the case; and never able to list a card on its own.** `name_index_key` is `number_index_key`'s twin and exists for the same reason — two sources spell one identity differently and neither is wrong.

**A card found this way is queued, never listed, and that is the owner's ruling.** Listing was offered and declined. Their words: *"I should be able to bulk clear them when the scenario is such that I have claimed that they're all a certain set that you have an excel for and that you have exact name matches."* The field that tells one card from another is precisely the field that could not be read, so the last check is a person looking at the photograph.

**It costs one press, not one per card, and that is why queuing is affordable.** Every entry from this rung carries **one** candidate — the row the ladder chose — under **one** shared reason, and a uniform stack gives **one** shared condition string. That is exactly D29's group-answer eligibility, so box 2's 45 are one `G`, one Enter, and one `U` to reverse, over a grid of their photographs. No new screen and no new route: `routing.NUMBER_UNREAD_NAME_MATCHED` plus a label was the whole client change.

**The lookup string says `name?:` and not `name:`.** A row found because the product prints no number and a row found because we could not read one are different facts with different remedies, and both are printed on the RUN REPORT (D16 — the machine string stays greppable).

**It does NOT reach the queue entry, and this entry claimed it did until 2026-08-25.** `store/queues.py:QueueEntry` has no `lookup` field and `Queue.parse` drops unknown keys, so the string lives only in `JoinReport`'s output. The consequence is worth naming rather than papering over: a name-inferred card that does NOT resolve cleanly — `set_ambiguous`, or any ladder review reason — never reaches the block that stamps `number_unread_name_matched`, so its queue entry carries an ordinary reason with nothing recording that the row set was reached by name at all. The review screen draws its "matched by name" sentence off that reason code alone, so such a card is indistinguishable on screen from one whose number read fine. Carrying the lookup onto `QueueEntry` is the fix, and it is a schema change nobody has argued for yet.

**What would reopen this: a name that resolves to two cards in one set.** Measured at zero across box 2, but a set with two prints of one name would produce it. The behavior is already correct — two surviving rows means two candidates and an ordinary one-card review — but it has never been seen, and the group offer would correctly refuse it as `group_not_uniform`.

**It was a rule about Pokemon's lookup until 2026-08-29, and it was written as a rule about a read.** This entry argues throughout that the NUMBER is the field that fails and the NAME is the field that survives — a claim about photographs and models, with nothing game-specific in it. It was nevertheless implemented in the Pokemon lookup alone, so every game keyed by a printed identifier (`riftbound`, `one_piece`) returned an empty row set and stopped where Pokemon fell through to the name.

**The owner found it from the far end**, asking why cards whose rows are plainly in the export were sitting in the review queue as unanswerable. Run `2026-08-29-box1-01`, 133 real Riftbound cards: **4 unusable reads, all 4 zero-candidate `no_catalog_row`** — and a zero-candidate entry is refused by `POST /review/<box>/<index>/answer` as `no_candidates`, so those cards could not be answered at all, only skipped, every session, forever. Three carried a set-code prefix the Riftbound prompt forbids in as many words (`UNL • 140/219` for `140/219`, twice with a bullet and once with a middot — a model slip at 3 of 133, not a prompt gap), and **all three hold exactly one row by name**. One of them, `Hwei, Brooding Painter` at **$2.86**, is above D9's threshold: a listable card stuck unanswerable. The fourth read `Wuju Master` for the export's `Master Yi, Wuju Master` and correctly stays unmatched — the name it gave is not the name the export carries, so nothing can rescue it.

**Nothing about the rung is widened by this.** It still fires only on an empty result, so it is reached only by a card already bound for `no_catalog_row`; it still produces a queue entry and never a listing; it still answers `name?:` rather than `name:`. What changed is which strategies run it. `name_only` deliberately does NOT gain it: there the name IS the key, so there is no unreadable number to fall back from.

**The real finding was the shape, and it is fixed — the owner's ruling, same day.** Each game had its own `_lookup_*` function, and each re-implemented the same four-step ladder — build a key, look it up, try the blank-`Number` name, fall back to the name — differing only in STEP ONE, the only genuinely per-game part. D35 landed in one copy and nothing compared them, because nothing could: they were three unrelated functions that happened to be parallel.

`pipeline/join.py:_walk` is now the ladder, written once, and `KeyStrategy` is the per-game part as a VALUE — a key builder, the lookup label, and whether D35's rung applies. **A rung added to `_walk` cannot land in one game and not another**, which is the property the old shape could not offer at any level of care.

**The owner asked whether the exports differ per game, and they do not.** Measured across all four committed fixtures — SV09, the wide Pokemon export, Riftbound and One Piece — the 16-column header is **byte-identical** (one md5 between them), which is what makes a shared ladder correct rather than merely tidy. What is genuinely per-game is the `Product Line` cell, the rarity vocabulary, the shape of the `Number` cells, and one import file per game (D25) — none of which lives below step one.

**`name_only` keeps its exemption, and it is not compatibility debt.** `pokemon_code` has no collector number at all and lives inside the Pokemon export as a blank-`Number` row, so `rows_for_name` would match it to the NUMBERED card of the same name — a code card listed as the card it came with. The rung is for "we could not READ the number"; a product that prints none has nothing to fall back from. That is now a declared `name_rung=False` rather than an absence somebody has to notice.

**Behavior-preserving, and checked as such rather than asserted.** `join --dry-run` over both real runs — box 1's 133 Riftbound cards and box 2's 544 Pokemon cards — produced **byte-identical output** before and after the restructure.

Covered by T3 in both directions, observed failing against the old code first.

---

## D36 — The run says what the model read; the store says which slot it is in

**Built 2026-08-24, immediately after D35, because applying D35 exposed it.** A re-join of box 2 wrote all 47 queue entries **one position off** — every entry carrying the right read with its neighbor's slot, photograph and label. On screen: `Wally's Compassion` described over a photograph of an Inteleon. It was caught before it was answered; the queue was restored from a backup taken minutes earlier.

**Nothing about D35 caused it. Any re-join of that run would have done the same.**

**The two halves are each correct and the seam between them was not.** `cli/runs.py` makes a run an immutable input on purpose: it is what lets a Batch outlive the server that started it (D33) and what makes a run an auditable record of what was submitted and billed. D10 ruling 1 lets a junk capture be deleted from the middle of a box, sliding every higher card down one slot, and the store does that completely — records, photographs, sidecars and **both queue files** are remapped and a `renumbered` event maps every old index to its new one. Neither is wrong. What was wrong is that the run's POSITIONS were then read as truth.

Box 2: card `2/7` was deleted, 537 cards shifted down one, and the run directory — correctly unable to be rewritten — still described the box as it had been.

**The owner's reading is the one this is built to, and it is a better diagnosis than the three options they were offered:**

> *"It should've gone away and autocorrected all the others too... I don't see how these could've been disconnected."*

**So the run no longer owns the slot number.** It owns what the model read from a PHOTOGRAPH; the store owns which slot that photograph is in. `photo_sha256` is the join between them, it is on every run record whose photograph could be read, and it is the only binding that survives a renumber (a record whose photograph raised an `ImageError` carries `None`, which is the digest-less case below) — a slot number is exactly what moved. `cli/resolve.py:realign` runs before anything reads a position out of the payload, and the run directory on disk is never touched.

**Measured before it was chosen**: box 2's 543 photographs are 997 MB and hash in **0.56s**, to 543 distinct digests with no collisions. Reading the photographs is affordable per join and is strictly better than trusting the store's identification cache, which is another derived copy a future defect could leave stale in the same way.

**Five outcomes, reasoned per box, and the per-box part is not a detail.** The first draft reasoned over the whole run and declared **all 53 of box 1's cards departed** — because box 1's photographs have been deleted from disk while its records live on. That inverts the check: absence of photographs is absence of evidence, not evidence of absent cards.

- **moved** — the digest is on disk at a different slot. Re-bound, and named in the report.
- **departed** — the digest is on no photograph in a box whose *other* photographs are present. The card has left: deleted mid-box or retired. Skipped, because there is nothing to join it to, and **named** — `CLAUDE.md` forbids dropping a card silently, not dropping one at all.
- **ambiguous** — the digest is on two photographs. That is a question, not a slot, and guessing an identity is forbidden. Refuses the whole run.
- **collided** — two RECORDS carry one digest, so they re-bind to one slot. **Added 2026-08-25, and it is `ambiguous`'s missing twin**: that outcome checks the DISK for a digest appearing twice, and nothing checked the PAYLOAD. Two records landing on one key overwrote each other in the rebuilt payload — measured at two cards in and one card out, with `departed` empty and nothing printed. A silent drop inside the function written to prevent one. Refuses the whole run and names the contested slot.
- **unverified** — the box offers nothing to check against: no photographs on disk, no record carrying a digest, or no digest that matches any photograph there. Its records pass through exactly as the run recorded them, and the report says the slots were **not** checked, so an unchecked box cannot read as a verified one. The third case is why this is stated as "nothing to check against" rather than "no photographs": a box whose photographs have all been REPLACED (D26's re-shoot writes new bytes at the same slot) matches none of the run's digests, and calling its cards departed would be the same inversion the paragraph above refuses.

**A record with no digest is the fifth thing that can refuse, and it is not an outcome of a box.** `cli/cmd_identify.py` writes `photo_sha256` as `None` for any card whose photograph raised an `ImageError`, so a run written today can carry digest-less records — this is live, not merely a guard against payloads older than the field. Such a record is harmless while nothing in its box has moved and unplaceable once something has, so it refuses only in the second case.

**A healthy run returns the identical payload object**, which is what keeps its join byte-for-byte unchanged — verified against Gate B's box-1 run, which diffs clean.

**What would reopen this: a second binding that outlives a renumber.** `capture_id` is on the card record but not on the run record; if it were carried into the run payload it would be a cheaper key than hashing a gigabyte, and hashing could become the fallback rather than the primary. That is a change to what `identify` writes, not to this entry.

---

## D37 — A queued question can be closed without answering it, and the card is left alone

**A stand-down closes the question and writes nothing to the card.** Built 2026-08-25, settling a question this repo had carried open since the review screen was built. `docs/DESIGN.md` has said, for as long as Skip has existed, that Skip is an OPEN QUESTION rather than a decision: if nothing is ever skipped, delete the control; if most of a queue is, the screen needs a real defer that records a reason, and that is a decision entry rather than a button.

The owner pulled that trigger, asking why they could not mark something as a known skip — a stand-down on the flag — from the review window itself, for a card that is a wasted position.

**There were two ways past a card and both were wrong for this.** An answer writes a SKU onto a real card, which the operator must not do to a card they cannot identify — `CLAUDE.md`'s hard rule is that ambiguity goes to the queue rather than being guessed. Skip writes nothing at all and a reload forgets it, so a card that will never be answerable comes back every session, forever. Between *invent an identification* and *be asked again tomorrow* there was no third move.

**The third move is one flag, and the flag already existed.** `store/queues.py` was built around `cleared_by_human`: `Queue.upsert` refuses to re-queue a cleared position, `Queue.release` refuses to drop one, `open_entries` hides it. The machinery for *stop asking, and keep not asking across every future run* predates the review screen. The only thing that could ever SET it was an answer — and an answer costs a SKU. `POST /review/<box>/<index>/stand-down` sets the same flag with a reason and nothing else.

**It is a third thing, not a softer retirement, and the boundary is the entry:**

- an **answer** (D4) writes `sku` and `condition`. The pipeline is told what the card IS, and every later join reads it back as rung 0.
- a **retirement** (D26) writes a terminal state. The CARD left inventory; the record stays and the gap is permanent.
- a **stand-down** writes nothing to the card at all. It does not move, change, or leave. It keeps its slot, its photograph and its place in the box walk, and stays sellable if it is ever identified properly. What closes is the QUESTION.

**Its own three reasons rather than `master.RETIRE_REASONS`.** Those four — `pulled`, `damaged`, `lost`, `given_away` — all say the card is gone, and borrowing them would make *stop asking me* indexable as *this card has left*, which is the one thing it must never mean. `queues.STAND_DOWN_REASONS` is `wasted_position | cannot_settle | not_listing`, hand-authored in D22's sense and rendered verbatim beneath its human label the way every reason code on that screen is.

**The reason is required, and it is the instrument `docs/DESIGN.md` says was never read.** That file records Gate B's mistake by name: the run produced a real queue, the owner answered all of it, and *nothing counted how many were skipped first* — so the control stayed exactly as unsettled as it began. A stand-down without a reason would repeat that. With one, the log can finally answer which questions get waved off and why, beside `queue_reason`, the queue's own reason for asking.

**The canonical case is real and was found the same day.** Box 2 position 95 holds a photograph whose mean luma is **1.7 out of 255** — a black frame, captured at 3120x4160 where every other card in the box is 2160x3840. Haiku was shown nothing and returned `Mewtwo ex 009/102` at HIGH confidence; it matched no row, so it queued as `no_catalog_row` with zero candidates, which `POST /review/.../answer` refuses outright as `no_candidates`. That card could not be answered, could not be usefully re-shot, and came back every single session. That is `wasted_position`, and it is what this entry is for.

**The reversal refuses an answered card, which is the guard worth naming.** Both directions sit on one path (D28's shape, and `do_mark_sold`'s reason: a reversal reachable without going through the thing it reverses is a route a stale client finds on its own). Reopening a queue entry is the same store operation either way, so `_clearing_event` reads the log to learn which event closed the question and refuses `not_stood_down` when it was an ANSWER — taking back a real identification through the un-dismiss control is the one thing this route may not do. It inherits `_answer_before`'s `renumbered` hard stop for D10 ruling 1's reason: a clearing line older than a mid-box shift belongs to the slot's previous occupant.

**No listing hold is consulted, in either direction.** `undo_too_late` asks whether a SKU this Mac wrote is already out in an import file. A stand-down writes no SKU, changes no SKU and moves no listing count, so nothing downstream can disagree with it.

**The screen offers retirement beside it, and delete deliberately not.** Both were asked for in the same breath. `POST /inventory/<box>/<index>/retire` already existed and already had a client function; what it lacked was a control on the screen the card is actually on, which is `CLAUDE.md`'s route-is-not-a-feature rule in its mildest form. **The mid-box delete stays on `#/inventory`** for two reasons that are about this screen rather than about the operation: it slides every card behind it down one slot, so pressing it from a worklist would renumber the very positions that worklist is drawn from — the defect D36 was written to stop, invited back in by hand — and it is the one operation here with no undo at all. The panel says so on screen rather than leaving someone to hunt for it.

**One panel, keyed, because the difference is the hard part.** The owner's confusion was not about where the buttons are; it was that these are three different acts with three different costs, which no button label conveys alone. `X` raises a panel that names what each one does to the card, and it owns the keyboard while it is up for the group offer's reason — its choices are keyed on digits that mean candidates everywhere else on that screen.

**What would reopen this: the reason counts.** If `wasted_position` dominates, the fix is upstream — a capture that can produce a black frame at a different resolution than the rest of its box is a rig fault, not a queue fault, and no amount of dismissing is the remedy for it. That is the measurement `docs/DESIGN.md` has been asking for since Gate B, and this route is what finally takes it.

---

## D38 — The photograph is sized by the rows beside it, and the box and the runs get the third column

**The card photograph is sized for confirming a slot, not for judging a card.** Built 2026-08-25. `#/inventory` drew two columns — the box walk, and one 1004px column holding the card detail, the copies, then `BoxOps` and the run panel side by side.

Measured at 1440x900 on box 2 card 1 with six copies, by rebuilding the old arrangement in the live DOM: **body 1878px -> 1396px, photograph 420x587 -> 150x204**. The saving is data-dependent — most of what remains is the copies list, where a `position-bar` takes a line by rule — so read 482px as this card, not every card.

**The photograph had been sized against the wrong screen.** D33 gave it a `minmax(280px, 420px)` track arguing 280px was small because the review queue gives the same job 415x736. The two screens do not have the same job: the review queue is where a card is JUDGED, and this screen's question is *where is this card*. Borrowing a floor from a screen with a different job is the mistake `docs/DESIGN.md` names when it refuses to draw the Fulfiller's minimums on the owner's screens.

### Sized by the rows, then by its column

`.browse-facts` measures 203.5px, and 63:88 at that height is 145.7px wide — a 150px track, down from 420.

**It took its height from the facts for a few hours and is sized by its column again**, and the middle step is what made the right size findable. Pinned to the rows it was 150x204; the owner then asked for it back, which reads as a contradiction and is not. The two conflict only while the facts are as wide as they were: `Captured` printed a full ISO stamp at ~234px and now reads `6:35pm · Aug 23` at ~100px, so the widest value is the card's own NAME and the facts want ~270px instead of ~426px. `CardOps` moves up beside the facts, and the re-shoot control becomes a 24px icon with its words on `aria-label`.

**The frame went with it, deleting a class of defect rather than an instance.** While the photograph took its height from the facts the reservation had to live on a WRAPPER — and a wrapper holds whatever `PhotoPanel` returns, so a card with a missing file got a card-shaped box around a paragraph: measured 424x592 around 424x149, with the re-shoot control at y=985 of a 900px viewport. `aspect-ratio` is back on the `<img>`, where it cannot reach anything that is not an image. **Moving a reservation off the thing it describes and onto a wrapper gives it to everything else that wrapper can hold.** `align-self: stretch`, `.browse-frame` and a `:not(.is-absent)` media rule are all gone.

**`object-fit: cover` stays, against the obvious objection.** The frame is no longer guaranteed 63:88, so `contain` looks honest. D32 measured these frames at 2160x3840 with the card filling 80–88% of the width and 61–72% of the height, so `contain` would letterbox a narrow frame and shrink the card inside an already small photo. `cover` crops the desk off.

### The column, and what it cost on the axis nobody checked

The ~270px the photograph gave up became a third column for `BoxOps` and the run panel, which rewrites D33's last line: the row cost the card's column one panel's height, and the column costs it nothing.

**That was true about width and false about height.** A grid row is as tall as its tallest cell, and the card shared row 1 with the run panel while the copies were row 2 — so the copies began wherever the console ended:

| console state | console | copies at | whitespace | page |
|---|---|---|---|---|
| closed | 799px | y=938 | 378px | 1552 |
| a run picked | 1461px | y=1599 | 1039px | 2214 |

Picking a run is ordinary and the panel polls on a 4s/20s timer, so the second row is a resting state — the answer to *where is this card* positioned by something that is not about the card, at a height with no cap.

`.browse-body` is two columns and three rows: the walk, then the card, the copies and the console stacked in the content column. That voids D33's argument of 2026-08-24 for keeping the copies in the facts column — a 587px photograph would have pushed them off a 900px viewport, and no photograph here is that tall. **The console pays for its own move** — widened from 370px to 1024px it draws 625px closed and 1143px open with no code change, because its head stops wrapping four command names and its notes and free steps unwrap with it. What this entry got right and the rebuild keeps: the box belongs in the walk's column, the runs are not the card's neighbor, and nothing folds.

**What it costs:** `Check cost` was at viewport y=495 and is now below the copies. Identifying is done once per box; the copies answer the per-card question. If that trade is wrong the fix is to swap the last two rows, **never to restore the column**, which is the mechanism.

### Then the box left that column too

The owner, the same day: the operations should all exist on the left. The evidence was a duplication nobody had counted — `BoxOps` drew `Section 1 #1–#85  85 cards` as inert text for every divider, while `.browse-secthead` drew the same five rows a thousand pixels left, foldable, tickable and walkable. **The walk IS the sections list**, which is D31's finding one scale down, so the panel headed `Box 2` was the redundant instance.

`BoxIdentity` splits out of `BoxOps` for it — name, fill, state and the segment track, under the strip that names the box. The operations sit at the bottom of the walk. They sat there beside `RegisterBox` until 2026-08-26, when the owner deleted that control outright; nothing is lost, because `CaptureScreen.tsx:createOfferedBox` calls the same `POST /boxes` from the Box field. The sections list, its `Layout and controls` heading and the `sections 1 86 171 253 394` clause are **deleted rather than moved** — three renderings of one fact on one screen. The third column keeps the runs alone at 370px and the card takes the difference.

**A real defect came with that move.** `.browse-map` is sticky and capped at the viewport, so anything past the cap renders below the fold and the page scroll cannot bring it back. Harmless while the column held a search, a strip and a list; not harmless once the box's editors moved in, where opening the claims editor on a 720px window put the Apply button permanently off-screen. The column scrolls itself now, and `.browse-list` keeps a 6rem floor so an editor cannot squeeze the walk to nothing. `app/tests/inventory.spec.ts` asserts the escape hatch rather than the button's position.

### Density, to earn the narrower track

- **`BoxOps` drew one row per section with no bound**, at 25.5px, so the panel's height was a function of how finely a box happened to be divided. Box 2 declares five sections and draws **127px**, so the cap saves nothing today — what earns it is the other end, D31 recording **this same box at 22 sections**, ~560px, and D10 making dividers freely editable from any screen. Capped at six rows and scrolled, with the section total on the heading so a capped list cannot read as a short one. Row tracks narrow from 8rem/10rem to 5rem/7rem, moving the wrap cliff from ~399px to ~280px.
- **The run panel drew four 20px display headings**, the same size as its own title, so an open run said the steps and the panel were the same rank. 14px body now, matching `BoxOps`. Buttons drop to 32px, which is `.boxops-plain`'s height — the two panels disagreed about how tall a control is by 17%.

The column is then **`minmax(340px, 400px)`**, allocated after the cuts.

**Three columns are a >= 1240px layout.** 1240 rather than 1440 because the owner works at 1440x900 and a breakpoint at the working size is one you cross by un-maximizing a window; it also puts Playwright's 1280x720 inside the new layout, so `make design-check` exercises the three columns rather than only the fallback. **The number survived the columns (2026-08-26):** there is no three-column body any more and no body breakpoint at all, which deleted the `@media (max-width: 1239px)` block. 1240 now governs the CARD BAND's third track, and the reason transfers unchanged.

### Four things the card panel gained, from one finding seen in four places

- **`Rarity` and `Note`, which `CardOps` could overwrite without showing.** `ClaimEditor` writes five claims and the list drew three — and it opens with those fields empty and reads armed-and-empty as a CLEAR, so `Correct claims` was a blind overwrite of two values appearing nowhere on screen. `rarity_claim` is set on 543 of 543 records, so this was live. Rarity renders verbatim (D22), through the same renderer as the finish claim so a second `' · '` join cannot drift.
- **`Run` and `Confidence`.** `run` is on all 543 records and is the join between this panel and the run panel, which lists directories and cannot say which cards each touched. `Confidence` is the only place a RESOLVED card's hedge is readable, since `#/review` draws it only for a queued card. Shown FLAT, never as a chip or a color: T1's and D35's recorded misses are all confident and wrong, so `high` is not reassurance.
- **Whether the card has an open question, from `GET /queues`.** A queued card rendered `State: identified` and nothing else — and `state` there is MISLEADING, describing how far capture and identify got while the question was raised by the JOIN. The candidate count is load-bearing: zero candidates is the difference between *go and answer it* and *it cannot be answered as it stands*, which points at the re-shoot icon already on this panel. The label map moved to `app/src/reasons.ts` and is IMPORTED by both screens rather than copied — nothing keeps it in step with `pipeline/variant.py`, and the defense is making that drift visible. `scripts/docs-audit.py`'s reason-codes check follows it there.
- **The copies list spans the card's column AND the runs'.** Measured: in the middle column it was 976px of a 1450px page on the default card and 1713px of 2187px on an eleven-copy one, with 778px of viewport empty beside it. Wide, the row goes 144px to 82px and eleven copies go 1598px to 902px — **43% with nothing removed**. Keyed to a **container query** rather than a breakpoint, because `CardLocations.css` promises to be honest with no breakpoint to keep in step. It also collapses `detail`'s two render sites into one.

  **Amended 2026-08-26: the copies span the CONTENT COLUMN, the same width by another name** — 1024px at 1440 and 864px at 1280, the exact widths they had spanning columns 2 and 3, so every measurement above stands. Re-measured on the way past: a row is 83px at >= 940px of container, 115 at 864, 127 at 860 and 159 at 630. **The 860 threshold is therefore mis-set**, buying a 127px row rather than the one-line 83px one, and is left alone deliberately: raising it to 940 without guaranteeing the container is that wide would drop 1280 from 115px to 159px. The sharpest known defect in this area.

**The four rows closed the band's air and slightly overshot.** The facts are now 415px against a 349px photograph, so the ~90px under the facts is ~66px under the photograph. Which side is taller was never the property worth guarding; the assertion checks the two stay within a band of each other.

**What would reopen this: a photograph nobody can read.** If the owner opens the review queue to look at a card they were already looking at here, this screen has acquired the other screen's job, and that is worth naming before it is resized.

### The twelfth row is a price, and it is the first fact here that is not on the record

The owner, 2026-08-29, asked for `TCG Market Price` on the card summary with a note of how stale it is.

**The store holds no price, and that is D8 rather than a gap.** Every figure comes from the Filtered Export and `store/master.py` has no field shaped like money — so *what is this card worth* was answerable on `#/pricing` and on no screen the operator is standing at when they ask. The eleven rows above are `asdict(card)`; this one is a join.

**The edge is D46's, reused: card -> `run` -> that run's `pricing.json`.** `cli/cmd_join.py` writes that file on every join with each matched SKU's export row verbatim AND every position holding a copy, so a position resolves to a SKU and a Market cell with no new route, no new field on the wire and no schema change. `GET /pipeline/runs/<name>/pricing` is free and read-only.

**Keyed by position, never by `card.sku`** — the one decision here that could be silently wrong. That field is written by `emit`, so a sub-threshold card, a card withheld under D49 and every card in a run joined but never emitted all carry `null`. A SKU-keyed lookup would draw nothing for all of them and look correct on the rest. The position is on both sides and written by neither. `app/tests/inventory.spec.ts` prices a fixture card carrying `sku: null`.

**One read per run, cached by run name.** A real table is ~80KB for 50 SKUs and a box normally names one run, so walking a box costs one read — the argument `queued` beside it already makes. Keyed by RUN and not by box, because D33 scopes a run to a SELECTION inside a box, so two cards on one shelf can carry two tables read at two different moments.

**The age is never optional and `read` is never `as of`.** `join` is free and routinely pointed at a refreshed export, so a bare `$5.47` claims a currency the file cannot support. `GET .../pricing` answers `written_at`, the mtime of `pricing.json`, because the export is a CSV downloaded at an earlier moment nothing here can see. The freshest honest sentence is when the pipeline last looked: `$0.34 · read 3d`.

**It read `$0.34 · read 3 days ago` until 2026-08-30 and wrapped onto two lines on every priced card.** Measured at 1440: `.browse-facts` is 578px at `column-width: 260px`, taking two columns of 277px and leaving a **181px value track** at 9.1px per character — a budget of **19 characters**. `$0.34 · read 9 hours ago` is 218.4px. Six of the row's twelve outcomes were over the line, so this was the ordinary state of the row.

**It was never a copy problem.** The figure is variable-width, so no wording holds: `$30.81 · read 9h ago`, with the age already at its shortest, measures **182px — one pixel over**. Widening cannot rescue it either, since two columns of 277px is what 578 gives; shrinking the label track to its ink (80px, `CONFIDENCE`) and the gap to `--s2` buys 8px against the 47 needed. The row asks for ~230px in a 181px track.

**`ago` goes and `read` stays, which is a trade rather than an abbreviation.** `read` is what establishes that the age is the JOIN's; without it `$0.34 · 12d` reads as twelve days on the market. `ago` is redundant beside a past tense and is the wider of the two, 45.5px against 36.4px. Measured headroom for the figure: `· read 12d` leaves **8 characters** (`$1234.56` fits), `· 12d ago` leaves 9 but spends the verb, and `· read 12 days ago` leaves none.

**And the words were unbounded where the compact form is not.** `N days ago` grows with N, so a year-old join renders `read 400 days ago` — wider the longer it went unattended, which is the opposite of what a staleness reading should do. `Nd` is four characters until 2036.

**It is a second rendering of `sinceText`, not a second vocabulary.** That function forbids two spellings of *two days* sixteen pixels apart, and this panel draws both ages within one screen. The thresholds, rounding and `today` floor stay in one function and only the spelling is a parameter; a private helper beside `marketText` would have been the same rule written twice. **The queue age keeps its words**, drawn in `.browse-queued`, which is full-width and has never been short of room.

- **Rejected: an absolute date.** `$0.34 · Aug 29` leaves 10 characters and reuses `capturedText`'s form, the structurally cheapest option. It answers *when* where the question is *how stale*, and reads as the `as of` this entry refuses.
- **Rejected: splitting the age onto a `READ` row.** The only option that shrinks nothing, at 9px of list height. The owner chose the one line.

**The guard measures the row and pins the viewport.** `app/tests/inventory.spec.ts` already asserted what this row says in five places, and every one was green through the defect — a sentence written past the track does not fail an assertion about its text, it takes a second line. The new case counts the lines the value draws. **The suite's default 1280 cannot see it**: there the list is 506px, one column, a 410px track where every string fits. The whole defect lives at a width nothing in that file had rendered, so 1440x900 is the case. Mutation-tested: the old wording takes it red at 2 lines, the compact form green at 1.

**The mtime rather than a `joined_at` inside the table.** A field written into the file would be better data and absent from every run already on disk — precisely the runs a screen is opened over. The mtime needs no re-join and cannot drift from the bytes it describes; what it does not survive is the directory being copied, and nothing here copies one. T7 backdates the file and requires the route to report the backdate, because asserting against the live mtime is VACUOUS — the test joins immediately before the request, so a route stamping `time.time()` answers the same integer. That version was written, mutated to a clock, and **observed passing**.

**Five outcomes, five sentences, and the row is never conditional** — the rule `Rarity` and `Note` already follow, because a row that disappears leaves *this card has no price* and *this screen does not show prices* indistinguishable. No run on the card is `not joined yet`; a run with no table is `join this run`, the one refusal worth telling apart since its remedy is a join; a position the table does not hold is `no row in this run`, which is `no_catalog_row` and the review queue's business; and a **blank Market cell is `no_market_data`**, verbatim, because it is `pipeline/routing.py`'s own `NO_MARKET_DATA` and D9 is emphatic that a missing price is unknown rather than low. Rendering it as `$0.00` is what hands a chase card away at the floor.

**Three of those were cut to the same 181px, and the refusal lost half of itself.** `no row matched by this run` was 236.6px and `no pricing table — join this run` 291.2px — the second wider than any price this row can draw, so it wrapped in the one state an operator cannot reproduce. Only one half fits, and **the remedy is the half that survives**: `MARKET: join this run` already says a table is missing, and the sentence it is told apart from — `could not be read` — names no remedy, so the pair still reads as two failures. `no age` replaces `age unknown` on the same grounds, joining `none` and `not recorded`.

**The underscore is a ruling.** Spelled `no market data` it is neither the machine string nor a human label — the second vocabulary D22 refuses and D16 exists to catch — and it greps to nothing against `decisions.json`'s own `no_market_data` block, which is where such a card is priced by hand. So the row splits: plain English where THIS SCREEN has nothing, and the pipeline's own word where the PIPELINE said something.

**A reload re-reads it, and leaving that out was a live bug.** The cache is cleared on the reload counter and the READ was keyed on the run NAME alone, which does not change when a box is re-read — so the cleared entry was never re-fetched and the row sat on `reading…` permanently. A clear and its re-read are one gesture. It matters more than ordinary staleness: Reload is pressed after something downstream changed, and a join is what rewrites a price.

**Beneath `Run` and above `Note`**, the placement `Confidence` gets for the same reason: the price is not a property of the card but what one join found in one export, so provenance reads down. Both rows would be inexplicable apart.

**What this does not do: it does not put pricing on this screen.** No preset, no override, no snap, nothing writable — `#/pricing` is where a price is DECIDED (D49) and this is where one is READ. If this row grows controls it has acquired that screen's job.

**What would reopen this: a box whose cards span many runs.** The one-read-per-run cache is sized for a box identified in one go; a box assembled from a dozen ticked selections would fetch a dozen tables while the arrow keys walk it. The measurement is how many distinct `run` values one box's records carry — two today, across the whole store.

---

## D39 — The pipeline gets a route, and the selection is handed to it

**Built 2026-08-29, and it reverses D33's placement on the owner's instruction after a design consultation they asked for.** The question put to that consultation was narrow — should the runs panel stay on `#/inventory`, move to `#/review`, or take a route of its own — and the recommendation was to keep it where it was. The owner overruled it: *"I want to give runs its own tab for now, put it between capture and review queue."* `#/runs` is the route, `app/src/Runs.tsx` is the screen, and `RunPanel.tsx` is unchanged inside it.

**The argument against is D33's AND IT IS RECORDED HERE RATHER THAN DELETED, because it names the one thing that could go wrong.** D33 put the panel on `#/inventory` because a run is something you do TO a box, or to the cards you have just ticked inside it, and that screen is where both are chosen: *"a route of its own would have to re-implement the box strip, the search and the mass-select, and would then be free to disagree with them about what is selected."* That sentence is still true, and it is the specification this build was written against rather than a prediction it disproved.

**The box is re-answered and the selection is not re-implemented, which is the whole of the design.** The two halves of a scope have different costs and the answer splits on that:

- **A box picker is cheap and cannot disagree with anything.** `#/runs` draws its own strip from `GET /boxes` — thirteen chips carrying a card count each, the same idiom the walk's shelf strip already uses. There is no second source of truth about which boxes exist.
- **A ticked selection is expensive and would.** `BoxBrowse`'s mass-select is the ONLY one in the product, and it is also what a box-wide claim correction reaches, so two of them would be two answers to what "the selection" means. So there is still exactly one, and `#/inventory` HANDS IT OVER: `app/src/runHandoff.ts` carries the box and its indices through `sessionStorage`, and `#/runs` draws what it was handed with a control that says where it came from and one that gives it back.

**The handoff is D27's CARVE-OUT AND NOT A NEW ONE.** That entry opens session storage to state that is device-local and meaningless anywhere else, against `CLAUDE.md`'s ban — a ban D13 imposes so two devices cannot disagree about where a card IS. A tick list is not where a card is. The key is `pkmnscan.run-scope`, it is declared in one module, and every reader and writer in the app goes through that module's three functions.

**It is not cleared by being read, and it is cleared by every other route into the screen.** A reload during a live run is ordinary — the panel polls, and an identify run takes minutes to hours — so a read-once handoff would silently drop the operator from "36 ticked cards" to "the whole box", which is a change to what the next press spends money on. What clears it: the operator's own control, picking any box on `#/runs`, and **arriving from `#/inventory` with nothing ticked**. That last one is the case that is easy to miss and the reason the control on `#/inventory` writes on every press rather than only when there is something to write — without it, ticking cards, going over, coming back and pressing again would restore yesterday's selection from storage.

**A carried box that no longer exists is dropped whole**, checked against the registry on arrival, because `runHandoff.ts` can validate a shape and only the screen knows which boxes are real. Falls through to the picker, which is where the operator would have been had nothing been handed over — D3 rung 0's rule one register down.

**Nothing is scoped on arrival, and that is a state the old address never had.** On `#/inventory` the walk had always picked a shelf by the time the panel drew, so `scope.box` was never null in practice. `Runs.tsx` refuses to default it: a box chosen for the operator is a box they did not read, and the next press after it is the one that spends money. The free preflight is disabled until a box is picked — **disabled rather than absent, and it is the one control on this screen that gets to be.** `docs/DESIGN.md`'s absent-not-disabled rule is about the control that COMMITS; the spend button still does not exist until the preflight has answered. This one is free, it is the next thing to press, and a control that vanishes until an unrelated press brings it back is a screen that looks broken.

**What the move buys, and it is the half D33 could not.** `App.tsx`'s own route table calls `#/inventory` a `look` route — "reached when asked, not on a rhythm" — and housed the four commands there, which are the loop a session actually is. The panel is also the tallest thing this product draws (625px closed, 1143px with a run picked), and on `#/inventory` it was the last row of the content column, which put `Check cost` a page-scroll below the card. Neither was going to be answered by a fourth relocation inside one screen; D38 records the three that were already tried.

**`,R` reaches it and the review queue moved to `,Q`** (the owner's instruction, in those terms). `App.tsx` said every route's chord key is its own INITIAL, and that claim is now false and is rewritten there rather than left standing: two routes start with `r`, `#/runs` has no second word to fall back on and the review queue does. What survives is the rule that actually makes it learnable — the key is a letter the owner would say out loud naming the screen.

**WHAT STAYS ON `#/inventory` IS ONE ROW, AND IT MUST NEVER BECOME TWO.** `app/src/BoxRuns.tsx` sits in the slot the panel vacated and does exactly two things: it says whether anything is running over the box in front of you, and it is the handoff. **No step, no console, no figures, and above all no control that spends** — D33's money gate is two presses that must both happen where the estimate is on screen, and a spend reachable from a screen that never drew a preflight is precisely what that gate exists to prevent.

**The live-run line is there because it is the one fact whose latency matters.** `identify/batch.py` logs only when a batch's status CHANGES, so a console written forty minutes ago is indistinguishable from a hang — which is why a run row says how long it has been running rather than inventing a progress bar. Whether the box you are standing at has one going is worth a line on the screen you are standing on; everything else about a run is a page away and should be.

**A grid defect came with the move and is fixed here, and it was caught by this repo's own test.** `.browse-map` spans `grid-row: 1 / -1`, and a grid item spanning several AUTO tracks has its height distributed across them. That was invisible while the console sat in row 3 at 625–1143px, because row 3 alone exceeded the sticky map's viewport cap. With a 50px status line there instead, the map's ~700px went into rows 1 and 2 — measured, a query matching no card put the runs row at y=266 with nothing above it. The last row is `1fr` now, which excludes it from that distribution. The case that went red is the one D38 wrote for the opposite defect, which is the argument for having written it as a measurement rather than as a class name.

**The two queue figures became the way into the queue.** `join` writes a review queue and the panel reported its depth with no route out of the report — a capability with a screen, and a screen with no way to it, which is `CLAUDE.md`'s route-is-not-a-feature rule in miniature. Both `Review` and `Parked` link to `#/review`; parked is not a second route, because `ReviewQueue.tsx` draws both files and its reason chips filter between them.

**What would reopen this: the handoff going unused.** If runs are never started from a ticked selection, the mass-select coupling this entry spends most of its length preserving is decorative, and the honest simplification is to delete `BoxRuns`' handoff and leave the status line. The measurement is `scope.cards` being non-null on any run in `runs/`, and `docs/GATES.md` step 15 still records that no run has ever been started from the app at all.

---

## D40 — The screen is three columns: the box, the card, and where its copies are

**`#/inventory` is three columns — the box walk, the card, and its copies — at roughly 22/33/45.** Built 2026-08-29, on the owner's own layout. Their words, after being shown the two-column screen: the run box at the bottom and the whitespace to the right of the card photo and description were seriously triggering. Then the design itself: think rule of thirds, the left third sidebar stays put, the middle gets the photo then the correct-claims and remove-card buttons then the description, and the right gets the card locations — maybe 20/35/45.

**The two complaints were one defect, three days old.** `2ec06f8` deleted the body's third column (D38, amended) and re-created it one level down as `.browse-detail`'s third track — `minmax(0, 1fr)`, a RESIDUAL track, so it absorbed every spare pixel in a 1024px content column and held two buttons in 408 of them. Measured: 408x374 of track holding 408x32 of content, **91% empty**, and that track was 40% of the content column's width. The stacked full-width copies list below it was the other half of the same problem — a band that could not fill 1024px, stacked on a list that needed it.

**The file had already confessed it and bet on a justification that did not hold.** `BoxBrowse.css` called the space the residual, named rather than dressed up, and defended it as the rail's declared growth room for the open-question block. Measured on the owner's store the day this changed: **both queue files were empty**, so that block drew on **0 of 543 cards**. The same comment also asserted that this is not the space the owner named — it guessed the complaint was the photo-facts gap. The owner has now named it, and it was the rail.

**The ratio is 22/33/45 and only the first number is derived.** At 1440 the body is 1408px and two 24px gaps leave 1360, so the owner's 20% is 272px — **8px inside the ~280px wrap cliff** `BoxOps.css` was tuned to clear (D38). 22% is 299px. A 285px floor holds it above the cliff at 1280, where 22% of 1200 would be 264. `fr` rather than percentages, because percentages plus two gaps overflow a container that has no slack to absorb it — `.browse-map` is sticky and would be the thing clipped.

**The description left the middle column, and that is the one place this departs from the owner's spec — at their own suggestion.** They asked for photo, then buttons, then description, stacked. It was built that way and measured, and the arithmetic refuses it: the middle column has 715px above a 900px fold, and photo plus buttons plus eleven fact rows needs ~1050. Capping the photo to fit costs it twice — **311x435 (1.35x today) AND 165px of dead slack beside it**, because a height-capped photograph that keeps 63:88 gets NARROWER than its track. The owner then proposed the answer themselves: the description could sit as an aesthetic thing at the top of the locations on the right third. That is what shipped.

**What it buys, measured at 1440x900 on box 2, card 1:**

| | before | after |
|---|---|---|
| photograph | 268x374 | **449x627**, aspect 0.716, **2.81x area** |
| description | 300x318, one column, in the band | 578x171, **two columns**, capping the copies |
| run line | y=1164, 264px below the fold | **y=62**, in the header |
| copies, first row | y=626, 82px rows, 3.35 visible | y=379, 144px rows, **3.62 visible** |
| ink / void | 33.34% / 41.99% | **47.97% / 26.30%** |
| page | 1230 | 1273 |

**Void is a measured number and the target was missed.** The owner asked for less than a fifth of the whitespace. Against an instrument that rasterizes every text and image rect at 8px and keeps only empty area more than 24px from any ink — so normal line-leading does not count and real holes do — the honest result is **41.99% to 26.30%, a 37% cut, not 80%**. Recorded as a miss rather than rounded up, because the owner's own rule is that a number is evidence. What binds it is the copies rows: the largest surviving void component is inside them.

**The copy-row re-tune was asked for and is refused, on the file's own rule.** The owner approved narrowing the row toward D38's measured 83px. At the 586px this column gives it, the row is `8 + place 51 + gap 12 + bar 65 + 8 = 144`, and line one already uses **583 of 586px** — so the position bar genuinely cannot join it. Lowering `CardLocations.css`'s 860px container threshold to 560 does shorten the row to 129px, and it does it by squeezing `.card-locations-place` to 231px, which **wraps the position label**. That file forbids exactly this: the position label is the string somebody carries to a shelf and it must not break. A row that is 15px shorter and lies about where a card is, is not a trade this repo makes.

**And the re-tune turned out not to be needed for its stated purpose.** The column move alone takes rows-visible from **3.35 to 3.62** — the rows are taller and there are more of them on screen, because they start 247px higher. The owner's *tighter width wise yet longer height* is what a 144px row at 586px IS; it was the goal, not the defect.

**The refusal above was of one mechanism, not of the goal, and a different one shipped the same day.** What is refused, permanently, is lowering the 860px container threshold: it buys 15px by squeezing `.card-locations-place` to 231px and wrapping the position label, which `CardLocations.css` forbids by name.

What was missed while writing it is that the row's dead space is not in its first line at all — it is inside the BAR. The bar is four stacked full-width children (box track 16, its caption 14, the section block's 8px track and its own 14px caption) on 570px lines carrying captions that measure ~120px and ~200px. **Beside their tracks instead of under them, the same four parts are two rows rather than four**: bar **65 to 34px**, row **144 to 114px** at 1440 and **188 to 158px** at 1280, copies visible on landing **3.61 to 4.56**, page 1274 to 1092, and the landing void **26.30% to 22.32%** — which takes the cut from this file's own 41.99% baseline to **47%**.

**Nothing is given up for it, and that is checked rather than asserted.** The box track is still 16px, the section track still 8px, the section block keeps its indent, and the captions keep their `#` and `Section` prefixes — all three cues `docs/DESIGN.md` names for telling the two scales apart. The position label stays on one line at 586px.

**The case that guards it had to be pinned to 1440 to be worth anything**, and that is the finding worth keeping: this suite runs at 1280, where the container is 528px and the rejected threshold change behaves identically to the shipped one. Written at the default viewport, the case passed against the very mutation it exists to catch. It is red at 1440 against that change and green against this one, observed both ways.

**And the fold exposed a cliff pointing the wrong way, which is fixed here (860 to 880).** `CardLocations.css` switches the bar into the row at a container threshold, and 860 was chosen against a 144px narrow row. Once the narrow row was 114px the wide branch was producing **126px at the exact width it engaged**: measured across the sweep, 820 to 114, **860 to 126**, 880 to 85, 900+ to 82. Crossing into the better branch made the row twelve pixels taller.

**It was dormant rather than invisible, and that is the worse condition.** The copies container is 612px at 1440 and 528px at 1280, so `min-width` needs roughly a **1980px viewport** to fire at all — nothing in the suite and nothing on the owner's display would ever have rendered it. 860 was picked because columns 2+3 measured 862px at Playwright's 1280, a layout this very entry deleted, so the number was inherited from a dead premise. That is the same defect D41 found in the position label's own comment, in a rule that had no way to fail while it waited.

**The assertion is the PROPERTY, not the new number**: a container that grows may never make a row taller. Pinning 880 would go green on any later change that moves the cliff somewhere else, which is exactly how this one survived.

**What it costs, named rather than buried.** `.boxops-meta` wraps from one line to two — 17px to 33px — because it needs the full 360px track and now has 299. Measured across 299-360px: it is one line at 360 and two below it, with no intermediate. Accepted rather than fixed: it is a metadata line, not a control, in a sticky column that has ~290px of unused height at the owner's size, and holding 360px for it would cost the description its second column.

**The run line is in the header, which is D39's rule held rather than spent.** `BoxRuns` is box-scope content that was living in the content column, so its y was set by the copy count and by whether the claims editor was open — measured, **y=1164 on a six-copy card and y=1572 on an eleven-copy one**, both below the fold. `docs/DESIGN.md` authorizes the header directly (the page title shares a line with the screen's controls and counts), and it was the one item on this screen missing that file's own first-row-of-content-within-150px floor, by 1014-1422px. D39's *it must never become two rows* stops being a promise in a comment and becomes structural: on a shared line it cannot. The left column — where D38's *the left column IS the box* would point — is **rejected by measurement**, not preference: its content box is ~334px and the ordinary ticked state is 428px, so it would wrap to two lines the moment anything is ticked.

**This is the fifth relocation of that slot in four days** (third column, row 3 of the content column, `#/runs` for the panel, row 3 for the line, header). Said plainly because D38 records the first three and a reader is entitled to count. What moved this time is a 32px status line, not the 625-1143px panel that made the earlier moves expensive.

**What would reopen this: a copies column wide enough for an 83px row.** That needs ~860px of container, which three columns cannot give at 1408px of body. If the owner ever works at a width where 45% exceeds 860 — a 1920px display puts it at 828, still short — the row improves on its own through the container query already there, with no change to this entry.

---

## D41 — The address is a rank, not a list, and the separator is deleted rather than replaced

**A position renders as a rank: a muted two-line path with the card number beside it at size, and no separator at all.** Built 2026-08-29, from a design pass the owner asked for and then chose from — they had never liked the dot theme, and the sidebar's own dotted line was going to two lines. Two designers worked it from opposite lenses and six treatments were rendered against the real store; the owner picked the **terminal-dominant** address and the **census-triad** meta block.

### It was not a font-size problem

`Box 2 · Section 1 · Card 14` is 27 cells at Martian Mono's measured 0.70em advance = **453.6px**, in a track that is 448.8px at 1440 and **387.1px** at 1280. It overflowed by 4.8px and wrapped. Of those 27 cells only **four are digits** — 67.2px, **14.8%** — while the words, dots and spaces are **386.4px, 85.2%**. The chrome alone is larger than the entire 1280 track. Shrinking to fit needs **17px**, and `CardLocations` prints the same string at 13px seven rows below on the same screen, so the fix the owner pre-emptively refused would have made the answer 4px louder than its own footnotes.

**The comment justifying the old size had already been falsified by a layout change.** `BoxBrowse.css` read that the worst realistic label — `Box 100 · Section 12 · Card 543` — draws 521px inside a 630px track, so nothing reflows. The px figure is right (520.8). **The 630px track no longer exists**: D40 made it 448.8px. A later change deleted the premise and left the conclusion standing, which is exactly the failure `docs/DESIGN.md` and D16 are both written against. Recorded here rather than quietly corrected, because the class matters more than the instance.

**The three parts are not equal, and the old rendering claimed they were.** `Box 2` is the drawer you walk to, `Section 1` narrows it, `Card 14` is the slot. On THIS screen the first two are already answered everywhere the eye lands — the box strip, the identity block, every section header, every copies row — and the literal string `Box 2` renders nine times in the document. `Card N` is the only part this panel uniquely supplies, so it is the only part drawn at size: the path becomes an 11px muted two-line stack and the slot a **44px** figure. The payload goes 24px to 44px, **+83%**, on a screen whose whole question is *where is this card*.

**The separator is gone, not restyled**, which answers the owner literally. Nothing takes the interpunct's place — with the path stacked and the slot beside it there is no seam left to mark. `.browse-position-joint` is deleted; that rule was itself only three days old (2026-08-26, painting the dots muted so the parts would bind), treating the joints as the thing to quieten where this treats them as the thing to remove.

**The server string is untouched and is still the accessible name.** `pipeline/join.py:Position.label` emits `Box N · Section N · Card N` and keeps emitting it. `PositionParts` recomposes it into key/figure pairs for THIS screen only and carries the original verbatim on `aria-label`, so a screen reader announces exactly what the store said — which is what makes a client-side split a VIEW rather than a quiet edit of the record.

**`app/tests/fulfillment.spec.ts` is not reached, and this was checked rather than assumed.** Its 32px tabular-figure floor probes `.fulfillment-place` and `.card-locations-place-large` inside `view(page)`; `.browse-position` is neither, and no spec selects it. D31's rule that the Fulfilment spec stays unweakened is intact.

### The sidebar is the same complaint with the scarce axis inverted

`cards 543 · sold 0 · fill 543 · next index 544` is 46 cells = **354.2px** in a track D40 narrowed to 299px at 1440 and 285px at 1280. It is **not** a digit-count problem — box 1's four-characters-shorter line wraps identically — it is four label words and three interpuncts, **277.2px of chrome against 77.0px of digits**. Here horizontal is fixed and **vertical is ~290px of unused height** under the column in D31's resting state, so the block flows DOWN instead of across: three census figures at 16px in a row, `next index` on its own line at the muted register.

**`next index` leaves the row because it is not a fourth statistic.** `cards`, `sold` and `fill` describe what is in the box; `next index` is D10's high-water mark — what the allocator will hand out next. Four peers joined by dots was a false claim about them, and the structure is now the distinction rather than a sentence explaining it.

**D20's two words are on screen once, on the identity line.** That entry is explicit that a denominator whose meaning switches silently between an open box and a sealed one is the failure it exists to prevent: `fill` is a fill-**so far** while the box is open and a frozen capacity once **sealed**.

**The qualifier was put on `.boxops-meta`'s fill and taken off again one commit later**, and the correction is worth recording because the first version made a duplication EXACT that had until then been approximate. `BoxIdentity` sixteen pixels above already renders `133 so far`; adding the same two words put the identical string on screen twice, nine words apart. **The field stays and only the qualifier goes**, which is the half that matters: `BoxOps.tsx` promises these key names grep to `inventory.json`, so dropping `fill` outright would have broken one promise to keep another. D20 is discharged either way, because its rule is that the number is unambiguous ON SCREEN, not that it is annotated at every site.

**Field names stay verbatim in the DOM.** The keys are written lowercase and uppercased by `text-transform` at paint only, so a copy out of the DOM still matches the store. `app/tests/inventory.spec.ts` asserts the lowercase text, and a `toUpperCase()` in the component — identical on screen — takes it red. That mutation was run.

**What it costs, measured.** The address block goes **86px wrapped to 70px**, shorter than the state it replaces. The meta block goes **33px to 62px**. That height is free in D31's resting state and is **not** free once a section is open, where `.browse-map` is at its viewport cap and `.browse-list` is the scroller — there it comes out of the walk at 25.5px per card row, about 1.2 rows. The ledger variant also rendered cost 81px and ~1.9 rows, and was declined on that number.

### Full treatment for all, the same day

The owner reopened it in those words. The paragraph this replaces named `.review-position` and `.card-locations-label` and said taking the treatment to them was a decision about all three sites — **and the count was wrong**: the capture screen draws the address in **five** more places, three of them inside running sentences. Six owner sites, not three.

**The structure is universal and the size is per site**, which is what the old paragraph's warning buys. It predicted that a 44px figure repeated seven times in a list would be a different and worse defect, and that is now measured: at 44px the copies row goes 114.17 to **126.48px**, +86px on a seven-copy list, and copies visible on landing drop 4 to 3 — on the screen whose recorded complaint (D38 twice, D40 again) is that the copies scroll away. So what is shared is the RANK — muted stacked path, no separator, the slot as the only thing drawn at size — and each site sets its own figure.

**One component, `app/src/PositionLabel.tsx`, and one declaration per site.** `--pos-slot` is the figure and `.position-num` is `1em`, so a site's whole register is one line in its own stylesheet. The key is `clamp(var(--pos-path), 0.295em, 13px)` — 12.98px at a 44px figure and 11px at 32, 28 and 20 — so `#/inventory` keeps its shipped key to within 0.02px and no other site declares one.

**Proportional scaling was tried and refused, with the arithmetic.** The shipped ratio is path 11px against 44px, 0.25em. At the review head's 32px that is 8px and at the copies row's 28px it is 7px, below anything this product draws. Probed independently, **all four new sites landed on the same 11px path against four different figures** — the path tracks each screen's metadata register (`.review-machine` 11px, `.card-locations-boxname` 10px) while the figure tracks its payload. Two scales, not one; a single multiplier would have claimed these screens are scaled copies of each other.

**The figure is free up to 32.3px, and that is one measurement not five.** The two-line path is 33.9px, so at `line-height: 1.05` every figure to 32.3px draws the same 33.9–34.0px block: 20, 24, 28 and 32 cost nothing, 36 costs 4px and 44 costs 12. **It is a property of a THREE-part label** — a two-part label has a one-line path and the plateau collapses, which D36 and D24 both contemplate.

**Three sites needed a rule the band did not.**

- **The copies list leads with the SLOT, not the path**, because it is a list. Down seven rows the coarse parts are identical, so path-first stands seven `BOX 2 / SECTION n` blocks in front of the only thing that differs — the dense-gray-table failure `docs/DESIGN.md` names by the front door. It is height-free **only because the two-line path absorbs `.card-locations-boxname`**; a box with no name pays +17px on every row, and D20 made names unique but deliberately NOT required. Latent today, and nothing warns.
- **An in-sentence label gets the RANK without the geometry** — the `run` form. Stacking inside a sentence measured 79px against 23px and orphaned the trailing period onto its own line; at `inline-flex` it rendered `BOX 2` above the baseline as a superscript footnote marker.
- **A numeric guard, which the splitter did not have.** `#/inventory` draws only real positions. `#/review` draws D24's pooled label `Pokémon code cards · pooled`, which the shipped splitter turned into a path reading `POKÉMON CODE cards` and a lowercase word promoted to a 300.9px figure. Nothing broke geometrically and no assertion saw it. A promoted slot is a slot NUMBER or the label renders whole.

**The Fulfiller's firewall is the component graph, not a selector.** `Fulfillment.tsx` and `CardLocations.tsx:FulfillerCard` do not import the component, so no `.position-*` rule can reach his 32px and 36px labels — which is why stripping a class prefix cannot breach it. The breach that would actually happen is somebody lifting the call out of `OwnerCard` into a shared render path, and `app/tests/fulfillment.spec.ts` now states that as a CAUSE (`.position-parts` count zero) rather than leaving it to be diagnosed from a font size. Mutation-tested: the lift takes the firewall case red, and eleven other cases with it.

**Two assertions were found defective on the way, both written earlier the same day.** `inventory.spec.ts`'s `labelLines` read `getClientRects().length` off a column-flex child, which is blockified and returns exactly ONE rect however many lines it holds — measured on the shipped tree, the label wraps to 2/3/4 real lines at 200/120/80px and the assertion read 1 every time. Its case only ever went red on a different assertion, which hid it. And `review.spec.ts`'s `.not.toHaveText(/Card 14$/)` would have gone vacuous the moment the DOM text stopped containing that string, passing forever while detecting nothing — the silently-weakened shape D16 forbids. Both now assert against `aria-label` or a geometric fact.

**What is not treated, and why.** `.review-row-position` (11px, 23 in the rail), `.review-group-pos` (10px) and the capture screen's bare-integer consumer keep the plain string: the mechanism is RANK, and a 10px caption has no rank to spend — stacking it would cost height in the two lists whose only job is to be scannable. The consequence is honest: **`#/review` now renders the address two ways.** So does `#/inventory`, where the band's 44px figure and the copies list's 28px sit ~500px apart in one idiom; the 1.57 ratio is what keeps the band dominant, and it is the first thing to look at if the screen starts feeling noisy.

**One site is untreated for a structural reason rather than a design one.** `CaptureScreen.tsx:1931` composes `Note saved on ${target.card.label}.` as a plain STRING inside a notice payload — there is no element to style and no JSX to return, so it cannot take even the `run` form without changing the notice type across the component. Named here rather than silently left, because it is the one place the owner's *all* is not satisfied.

**What would reopen this: a two-part label, or a box with no name.** Both collapse a measurement this rests on — the first ends the 32.3px free plateau, the second costs the copies list 17px a row. Neither is hypothetical: D24 pools cards without positions and D20 leaves names optional.

**The mechanism was reused on the sentence under the label — see D30 (2026-08-30), which owns that argument.** Named here only so the trail exists; the one thing it does not share is that its payload takes position rather than size, two thirty-character names being unable to carry a 44px figure.

---

## D42 — main moves by pull request, and the guard is local because the server-side one is not for sale

**`main` moves only by a merged pull request, and two local git hooks enforce it.** Built 2026-08-29, after main moved under live worktrees twice in one day.

`637e2e4` was authored on one session's branch and fast-forwarded into main while three others were working on branches cut from it; `f5dcc2b` was pushed straight to `origin/main` during the session that wrote this entry. `origin/main`'s reflog is five consecutive `update by push`. Nothing in the repo had ever said a session may not do that, and nothing checked.

### Branch protection is not available here

Measured rather than assumed — both surfaces answer 403:

    GET repos/shivinate7/pkmnscan/rulesets                   403
    GET repos/shivinate7/pkmnscan/branches/main/protection   403
    "Upgrade to GitHub Pro or make this repository public to enable this feature."

Free plan, private repo. Going public is not an option: `CLAUDE.md`'s opsec rule makes a live unredeemed code card a bearer instrument, and this tree carries the enforcement for it. So the server-side gate costs a subscription, and the owner chose the local guard.

**It would not have closed this on its own**, which matters if the plan ever changes. Branch protection bites at `git push`. Both incidents moved main **locally** first, by which point every session cut from main is already on a different history. A gate at the remote would have caught the second and been silent through the first.

### Two hooks, because there are two ways out

- **`scripts/githooks/reference-transaction`** — main does not move in this clone. A ref hook rather than a commit hook **because the first incident created no commit**: a fast-forward merge moves a ref and runs no commit hook, and `git rebase`, `git reset --hard`, `git branch -f` and `git update-ref` are the same shape. Underneath they are one ref update, so that is the only place catching all of them and the only one no porcelain command routes around.
- **`scripts/githooks/pre-push`** — nothing pushes to main. `git push origin HEAD:main` never touches `refs/heads/main` locally and lands the commit anyway, so the first hook is blind to it. This stands in for branch protection and is weaker in one nameable way: it lives on this machine, so it protects this clone rather than the repository.

**The one legitimate move is to a commit origin already has.** That is the whole allow rule, and it is what makes the pair a workflow rather than a wall: a PR is merged on GitHub, `git pull` fast-forwards, and the commit was on the remote before it was ever on your main. It cannot be forged from inside a session, because a local commit is not on origin until something pushes it, and pushing to main is what the second hook refuses.

### The `old` column is not evidence

The payload is `<old> <new> <ref>`, so the obvious rules are *allow a no-op* (`old == new`) and *allow a creation* (`old` all zeros). Both are wrong, and believing them shipped two holes. Measured on git 2.39.3:

    git branch -D main              0000000... 0000000... refs/heads/main
    git branch -f main feature      0000000... 3f5f2cd... refs/heads/main
    git update-ref refs/heads/main  0000000... 8f06f47... refs/heads/main

Git reports zeros whenever the caller did not state an expected value, even where main exists at a real commit. A deletion is indistinguishable from a no-op and `branch -f` from a creation — the first draft waved both through, and main was genuinely deleted in the test rig. The hook decides on `new` alone and asks git for the pre-update value itself.

**It fails open on its own bugs, which is a trade rather than a weakness.** This runs on every ref update in every worktree of the clone, so a version exiting non-zero by accident breaks git for every concurrent session at once. The only non-zero exit in the file is the deliberate refusal; an unknown phase, an unparseable line or a missing git allows. Same rule `scripts/docs-audit.py:nested_worktrees` states for itself, and the same one `scripts/guard-opsec.sh` took after it over-triggered (D16).

### Installed into the git common dir

**This paragraph said something else for about an hour and both its claims were false.** It said to point `core.hooksPath` at the MAIN worktree's `scripts/githooks`, because that setting lives in the common `.git` dir so one value governs every worktree.

**Claim one, falsified within the hour of merging.** A working tree's contents are a function of its branch. The moment this entry landed on main, the main checkout was on another session's WIP branch that predated it, so the directory git read held **one hook out of three**. The guard was armed at zero and nothing said so — the silent-failure class this repo refuses everywhere else, reproduced by the fix for it.

**Claim two, falsified by running the test rather than reading the config.** `extensions.worktreeConfig` is **on** in this clone, and whatever creates `.claude/worktrees/` writes a per-worktree `core.hooksPath` into `.git/worktrees/<name>/config.worktree`, beside a `core.longpaths`, so it is that tooling and not this repo. **A per-worktree value beats the common one.** After an install that printed success, `git config --get core.hooksPath` inside a worktree still answered the old path and all four worktrees were unguarded. It was found by running the nineteen cases against the INSTALLED directory — `PKMNSCAN_HOOKS_DIR` exists for exactly this — and would not have been found by reading the config, because the config that lies is not the one you look at.

So `make hooks` copies the tracked hooks into `<git-common-dir>/hooks-armed`, points the common config there, and UNSETS the per-worktree override everywhere. `.git` is per-clone and no branch can empty it. Verified after: all seven worktrees resolve to the install, the installed copy passes all nineteen cases, and a live `git push --dry-run --force origin <branch>:main` is refused by name.

**It installs what git tracks, not what the directory holds.** The first version copied `scripts/githooks/*`, and this repo lived in iCloud Drive, which had made `pre-push 2` and `reference-transaction 2` beside the originals — so it installed five hooks from three files, two untracked and reviewed by nobody. Git dispatches on exact names so it would not have RUN those two, and the damage was cosmetic; the mechanism is not. `git ls-files` is the only enumeration meaning *the thing someone reviewed*, and untracked files present are reported rather than skipped.

**What is given up: the copy can go stale**, and a new worktree gets handed the per-worktree override again. Neither can be closed by a check without lying — the tracked file legitimately differs between branches, so *installed does not match this tree* is a fact and never a fault, and must never gate a commit. `make status` reports both instead, reading NOT ARMED whenever the effective path is not the install.

### A session may perform the merge when the owner says the word

The owner's amendment, 2026-08-30. The sentence that changes is *the owner merges it on GitHub*, and only that sentence: the two hooks, what they refuse and why are untouched, because none of that is about who presses the button.

**The permission covers both halves of the merge**, which is the owner's second amendment of the same day. An earlier reading granted only `gh pr merge` and left the clone permanently one commit short: a session that merged had to stop and *describe* the `git pull`, which is a handoff in the middle of one operation and leaves every later session cutting branches from a stale main.

**It cannot widen what is mechanically possible, and that is the safety argument.** Allow rule 3 of `scripts/githooks/reference-transaction` is `git merge-base --is-ancestor "$new" refs/remotes/origin/main` — move main to a commit origin already has — and the commit a merged PR produces IS that commit. So this reaches the prose and nothing else: it arms nothing, disarms nothing, edits no file under `scripts/githooks/`, and needs no escape hatch. **`PKMNSCAN_MAIN=off` is not what a session reaches for here** and must not become it; a session typing that variable has left this amendment behind.

### The local half is two states, and one question tells them apart

**The move is two commands and must be.** An earlier draft said `git fetch origin main:main`, which is the right shape for this clone — the hook's own refusal message suggests `git switch main && git pull`, and main is often checked out in no worktree at all here, so there is frequently nowhere to switch. What it missed is that the combined refspec updates both refs **in one transaction**:

    git fetch origin main:main
      255e33b..8e8973f  main -> main
      51492d6..8e8973f  main -> origin/main        <- same transaction

At `prepared` the hook asks `git merge-base --is-ancestor "$new" refs/remotes/origin/main`, and that read of `refs/remotes/origin/main` answers with the PRE-update value — so whenever origin/main has moved since your last fetch, `new` is a DESCENDANT of what the hook can see rather than an ancestor, and it refuses. **The evidence the hook consults is being written by the transaction it is judging.**

**This is not a hook defect and must not be fixed in the hook.** The repair that suggests itself — read the transaction's own `origin/main` line and credit it — is the mistake that file's header refuses for the `old` column: **a transaction may not be a witness for itself.** Trusting a caller-supplied line would let one `git update-ref` naming two refs assert its own permission. The hook asking git for state OUTSIDE the transaction is what makes it sound, and the cost is that the caller fetches first. Observed 2026-08-30 against a main that had moved under it, PR #22 having merged between the write and the run — not a rare alignment but the ordinary state of a clone running seven worktrees.

**Ask which working tree, if any, holds main:**

    git worktree list --porcelain | awk '/^worktree /{w=$2} /^branch refs\/heads\/main$/{print w}'

**Nothing printed — main is checked out nowhere:**

    git fetch origin && git fetch origin main:main

**A path printed — main is checked out there.** Added 2026-08-30 after PR #38, because `git fetch origin main:main` is exactly what git will not do to a branch somebody is standing on:

    fatal: refusing to fetch into branch 'refs/heads/main' checked out at '/Users/shivinate/Developer/pkmnscan'

**That refusal is git's and not the hook's**, and telling them apart is most of why this is written down. Everything else here is about a hook that refuses, so a session reading the word `refusing` reaches for `PKMNSCAN_MAIN=off`, which changes nothing because no hook has spoken. `git switch main && git pull` is unaffected and always was: `pull` is a fetch and then a merge, two transactions, in that order. The hook's refusals name themselves and print the variable; this one names a path. Pull in that tree instead:

    git -C <that path> pull --ff-only

**Neither form is newly permitted.** Both are two transactions in the right order, so the hook still asks `merge-base --is-ancestor` against an `origin/main` that demonstrably holds the commit.

**The unconditional shortcut is a footgun.** `git -C <main tree> pull --ff-only` is correct only while main is the branch in that tree. Run without the question above, in the state this entry describes — the main working tree on a feature branch — it fast-forwards **that feature branch**. It moves no protected ref, so no hook has anything to say, and the only symptom is a branch somebody else is working on having quietly advanced.

**Rejected: a `make` target that picks for you.** It would delete the choice, and the choice is not what goes wrong — the two incidents are main moving *unasked*. What it would cost is the thing this entry values: the move is a deliberate act on the owner's word, and a target reads as routine plumbing.

**What it costs is real and is this entry's own subject.** Advancing main reshapes what every live worktree is cut from. What makes it a decision rather than a repeat is the pair of conditions above: an explicit instruction, and only to a commit that was on origin first.

**That rejection is amended, and the sentence moves while the reasoning does not** (owner, 2026-09-01). `make merge` exists — `scripts/merge-pr.py`, `scripts/merge-selftest.sh`.

**The rejection was aimed at automating the decision, and the decision is untouched.** Whether this pull request gets merged stays the owner's word, per *The word* below: a bare `make merge` refuses and says there is no default and will not be one, `ARGS=<n>` is a preview that presses nothing, and only `ARGS="<n> --confirm"` acts. That is D33's instrument one register down — the route that can spend money refuses without an explicit field, and this refuses without an explicit number and flag.

**What is automated is the state lookup, which is not a choice anybody makes.** Which of the two forms above applies is a question with one right answer that git already knows, and *the unconditional shortcut is a footgun* two paragraphs up is the account of what it costs to get wrong: no error, no hook, a branch somebody else is working on quietly advanced. A session was being asked to remember a lookup; it asks git instead, and re-asks with `git rev-parse --abbrev-ref HEAD` before it pulls.

**It widens nothing mechanically, for the same reason the amendment above widens nothing.** It fetches origin first and then asserts `merge-base --is-ancestor <commit> refs/remotes/origin/main` — allow rule 3, evaluated before anything moves rather than discovered when the hook refuses. It never sets `PKMNSCAN_MAIN` and no refusal it prints suggests it. A commit origin does not carry is refused by name.

**`make help` lists it, and the plumbing worry is answered by shape rather than by obscurity.** Hiding the target would be security by not-being-listed, which this repo rejects everywhere else, and `CLAUDE.md`'s own rule is that a capability nobody can find is not done. The two raw commands stay in `CLAUDE.md` beside it: the wrapper must not become the only way anyone knows the answer.

**The footgun has a test that was green for the wrong reason first.** `scripts/merge-selftest.sh` builds an origin, a clone and a linked worktree in a temp directory. Its first draft put the other tree on a branch already at the commit a wrong pull would have brought it to, so the assertion could not fail — found by forcing the picker to always choose the pull form and watching it stay green. The branch is one behind its upstream now, that mutation turns it red, and the fixture asserts its own arming. Same lesson `githooks-selftest` records about git's own refusals scoring as a hook's.

### The main checkout going stale

**The SessionStart hook reports the main working tree left on a feature branch after that branch merged.** Added 2026-08-30. Everything above governs how main MOVES; this is the tree that holds it drifting a different way.

**Measured that day: 70 commits behind, on a branch merged in PR #43, serving the owner's real store.** Nothing was lost, because the branch was fully merged. What it cost was the live rig running behind four merged PRs while `make status` reported `0 ahead of main, 70 behind it` and nobody read it.

**`scripts/worktree-guard.sh` carries it because that runs unasked.** D43 puts the ports there for the same reason rather than in a target somebody has to remember.

**It reports and never switches.** `git switch` is the operator's to type, and a hook that moved the branch under a running server would be deciding for them.

**Ahead is the number that decides, not behind.** Zero ahead with a clean tree means the branch holds nothing main does not, so switching can lose nothing. Anything else says so and points at `make status`. A worktree on a feature branch is correct and is never reported.

### The word

**It comes from the owner in the conversation, and it is per-instruction.** Not a standing grant, not a mode, never inferred. It is the same shape as D33's `confirm` field one register down — that route refuses without an explicit field because the next thing that happens costs money, and this refuses without an explicit instruction because the next thing that happens is the branch every other session is cut from.

**The test is whether the owner NAMED THE ACT, not whether they matched a phrase.** Added 2026-08-30, after this paragraph cost a session a round trip: it said *"merge to main" is the word*, and a session reading that literally hesitated over a bare **"Merge"** — the verb itself, as a direct instruction. That is the word. So are *merge it* and *merge the PR*. What is not the word is approval that never names the act: *ship it*, *land it*, *looks good*, an approving review. **The line is naming the operation versus expressing satisfaction with the work.** A phrase list is a worse instrument, because a session matching on phrases both balks at a plain instruction and can be walked into a merge by anyone who says five particular words.

**The merge is one operation, performed whole, and a session does not stop between the halves to ask again.** This is the correction the owner asked for after a session merged on GitHub, reported that local main had not moved, and waited — a session reading the entry correctly, which is what makes it a defect here rather than there. One word, both halves: `gh pr merge`, then the fast-forward. If the second half refuses or cannot run, that is reported as the incomplete operation it is, not re-asked as though permission were missing.

**What it does not license**: a direct push, a force push, `git branch -f`, `git update-ref`, or a merge of a PR the owner did not name. All four are still refused by a hook, and none becomes available by the owner saying this word.

**The local fast-forward is split rather than refused whole.** The incident that list meant is `637e2e4`, a fast-forward to a commit on NOBODY's origin, and that stays refused by the hook rather than merely by this paragraph. What the word licenses is the fast-forward to the merged commit ON ORIGIN, a different move sharing a verb. The hook has always drawn that line; today the prose draws it too.

**Why this is safe to grant and was not safe to assume.** What was missing was never the owner's consent — they had it either time. It was any record that consent was required, and any mechanism that noticed its absence. Both now exist, so an explicit instruction is a decision rather than a default.

### The escape hatch and the evidence

**`PKMNSCAN_MAIN=off`**, spelled the way `PKMNSCAN_GATE=off` and `PKMNSCAN_DOCS=off` already are. One variable, printed in every refusal, because a guard with no visible way past it gets disarmed at the config instead — and a disarmed `core.hooksPath` takes the three opsec rules with it, the trade D16 already refused for the docs audit.

**`make githooks-selftest` is the evidence, and it runs in `make check` and never in the git hook.** D18's rule: it writes — a bare repo, a clone, commits, pushes. It has a second reason of its own that the docs audit's self-test does not: it exercises the guard by **violating** it, so a version on the commit path would be refusing its own commits. Nineteen cases, two of which were green for the wrong reason until the harness checked whose refusal it was — git declines to delete the branch you are standing on and declines to push what is already up to date, both without consulting a hook. A refusal now has to carry the hook's own marker to count.

**What it does not cover**: one machine's clone. A push from anywhere else, a commit in a different clone, and the GitHub web editor are all outside it — the exact gap branch protection would close.

**What would reopen this: GitHub Pro, or the repository going public.** Either makes rulesets available, and the honest response is to add one requiring a pull request on main and keep both hooks — the server gate for what reaches the repository, these for what reaches this clone's main. Not either/or: the two incidents were one of each.

---

## D43 — the port follows the store, because the store was already per-checkout

**Every checkout derives its own dev and capture ports from its own path, because every checkout already had its own store.** Built 2026-08-29. `store/files.py:home()` has always defaulted to `REPO_ROOT` — the checkout the code runs from — so every git worktree has its own `inventory/`, `runs/` and `captures/`. The capture server's port was the bare constant `8000` in all of them, and `app/src/server.ts` asked for `http://localhost:8000` whatever tree served it.

**A shared port over per-checkout stores is not a busy-port problem. It is a data-loss problem, and it runs in both directions.** Whichever server won the bind answered every tree's UI:

- a worktree's screens drive the owner's real 767-card inventory, on a branch, with whatever half-finished route that branch happens to define; or
- the MAIN checkout's capture screen — the one the owner actually shoots a box from — is answered by a worktree's server, and real card photographs are written into `<worktree>/captures/cards/` and deleted with the branch.

The second is unrecoverable and silent. Nothing on either screen says which process replied.

**Half of this was already fixed and the half that was left is the one that writes.** `app/devPort.ts`, earlier the same day, gave every checkout its own **Vite** port after `make design-check` in a worktree attached to the main tree's dev server, asserted `docs/DESIGN.md`'s floors against code the worktree had never seen, and passed. That entry's own reasoning is the argument here: the shared PORT is the whole fault. It stopped at Vite and Playwright. The capture server, which is the process that writes photographs and inventory to disk, kept the shared constant.

**`app/tests/inventory.spec.ts` had already written the bug report.** Its stubs are justified in a comment saying an unstubbed read is a request to whatever is listening on port 8000, which in this repo is the owner's actual capture server over their actual 767-card inventory. That is this defect, observed, worked around locally, and never filed.

### One slot, two ports

`sha256` of the checkout's canonical path, first four bytes, modulo 300. Dev is `5200 + slot`, capture is `8100 + slot`, so a tree reads as a pair — 5276 beside 8176 — and there is one number to recognize rather than two unrelated ones. **The main working tree keeps 5173 and 8000**, so every doc, the Makefile's help and `scripts/views.txt` stay true and the ordinary single-checkout workflow is untouched.

**Derived, not allocated**, for the reason `app/devPort.ts` already gives: the same tree answers the same port on every run, which is what makes a printed URL worth keeping and what lets `strictPort` tell *someone else is here* from *I moved*. Collisions are possible — 300 slots, a handful of trees — and are loud: Vite refuses to start, and the capture server raises `EADDRINUSE` rather than serving somewhere else. The remedy is to rename the worktree directory; the port follows the path.

**Two implementations of one algorithm, asserted rather than trusted.** Python serves and TypeScript addresses, and neither can import the other. `make port-agreement` runs both over the same real directories and diffs them, and it is in `make check` rather than the git hook because it needs node and the hook runs bare. **It was mutation-tested in both directions before it was kept** — moving the Python band takes the composed-port case red, and changing the slot width takes every path red. A check that cannot fail is not coverage; this repo already paid for that lesson at the multi-game prompt seam, where a differently-named identifier field would have parsed cleanly and joined nothing.

**Canonicalization is part of the algorithm and was the one real trap.** Both sides realpath the root before hashing — Node's `realpathSync`, Python's `Path.resolve()` — because `/tmp` is a symlink to `/private/tmp` on this machine and one worktree genuinely lives under it. The agreement test therefore feeds **real directories**: a path that does not exist canonicalizes differently in the two languages, so synthetic inputs would have tested the test rather than the code. `app/devPort.ts` was moved from `resolve()` to `realpathSync` for this, and it was measured first — every worktree in this clone answers the same slot either way, so **no existing dev port moved.**

**It is said in the three places a session actually looks**, which is the half that makes it reliable rather than merely correct. The owner's complaint was exact: the port reasoning existed only in a source comment, not in `CLAUDE.md` nor in any hook, so it was not reliable. So `CLAUDE.md` carries the rule; `scripts/worktree-guard.sh` — the SessionStart hook — prints this tree's two ports before any work begins; `make status` prints them and says outright when you are in a worktree; and `make server`'s banner names the store it is about to serve and warns when that store is not the main checkout's.

**`PKMNSCAN_PORT` overrides, the same knob and shape as `PKMNSCAN_HOME`.** An unparseable or out-of-range value is **ignored rather than obeyed**: a typo must not put the server on a port no client will look at, which is this entry's own failure arriving by another road. `VITE_CAPTURE_SERVER` still outranks the derived default on the client, because that is the operator's explicit override and the case `docs/specs/capture-app.md` §11 leaves open — the Fulfiller's device pointed at this Mac by address.

**What this does not do: it does not give worktrees a shared store.** Each still has its own, still usually empty, and that is D13's one-truth-on-the-Mac holding — the truth is the main checkout's. A worktree that wants to work against real data points `PKMNSCAN_HOME` at it deliberately, which is a decision with a visible env var rather than an accident of which process bound a socket first.

**What would reopen this: wanting one capture server for every tree.** The honest shape then is one server on 8000 with `PKMNSCAN_HOME` pinned to the main checkout and the worktrees' clients pointed at it by `VITE_CAPTURE_SERVER` — the knob that already exists. That is a different decision about where the truth lives.

### One file was missed, and it was the one a human looks through

`.claude/launch.json`, found and fixed 2026-08-30. It was tracked, and it hardcoded `"port": 5173` — right in the main tree and wrong in every linked worktree. `vite.config.ts`, `playwright.config.ts`, `server/capture_server.py` and `app/src/server.ts` all moved onto the derivation; the Browser pane's own launch config did not, so `preview_start` would start THIS tree's dev server on its own port and then open a tab on 5173.

**That is this entry's own defect wearing a different hat, and the worse half of it.** A dead tab is a nuisance. A tab on 5173 while the main tree's `make dev` is up is a worktree **previewing main and looking like it worked** — the same silent-wrong-answer shape `app/devPort.ts` records for `make design-check`, which that file calls the worst shape a check can fail in, because the only signal it gives is the one you were hoping for.

**A tracked file cannot hold a per-checkout value, so it stopped being tracked.** `.claude/launch.json` is gitignored and written by `make launch-config` from `server/ports.py` — the same derivation the other four read, so all five cannot disagree. It hangs off `make venv`, which is already the documented first step in a fresh clone and is what `make worktree-setup` calls; it is a standalone target as well, because **the port follows the PATH** and a renamed worktree needs it written again.

**The precedent is `.claude/settings.local.json`, already gitignored beside it.** The split inside that directory is not new: what every checkout shares is tracked, what one machine or one checkout answers is not. Nothing in the repo reads `launch.json` — no doc names it, no audit check resolves it — so this cost nothing but the file.

**What this gives up:** a fresh clone has no launch config until `make venv` runs, where before it had a wrong one immediately. That is the right direction for a file whose only failure mode is pointing somewhere plausible and wrong.

**And that trade was wrong about what an absent file costs, which took twenty-three days and a measurement to see** (2026-08-30). The paragraph above reasons that absent beats wrong. It does not, because **nothing leaves it absent**: the Browser pane's own instructions tell an agent that finds no `launch.json` to create one from a template carrying a literal port, so *absent* is a state that lasts until the first `preview_start` and then becomes *wrong* — written by a session that had no way to know this repo derives the number. Absent is not the safe end of that trade; it is the *entrance* to the unsafe end.

**Measured across the five worktrees of this clone**: four correct, one absent, and one — the tree the measurement was taken in — holding a hand-written **5173** nobody remembered writing. That is a linked worktree whose Browser pane would start its own dev server on 5470 and then open a tab on the MAIN TREE's.

**And the absent one became a 5173 while the fix was being written, which is the measurement that settles it.** `card-sku-stamping-fix-d11945` was the tree with no config at 10:16. At 10:29 it had one naming **5173** against a derived **5313** — written by a session in that worktree, from the template, in the twenty minutes between the two readings. Nobody was careless: the port is a fact about the checkout's path and there is no way to know it from inside a tool that offers a template. **The absent state is not a resting state, and it decays in exactly one direction.**

**The fault was that the fix was a Makefile target, and a target only runs when somebody runs it.** `make launch-config` hangs off `make venv`, which `make worktree-setup` calls — so it reaches a worktree provisioned that way and no other. The five readers this entry moved onto one derivation are all *code*, which runs whether or not anyone remembers; this one was a file somebody had to ask for.

**So `scripts/worktree-guard.sh` writes it, and that is the whole of the repair.** The SessionStart hook already runs before any work starts in every checkout, already provisions the other gitignored things a tree cannot inherit, and already imports `server/ports.py` to print the pair. One more provisioned thing, from the one derivation, with nobody required to remember a target. **It runs ABOVE the worktree test**, because `dev_port()` answers 5173 in the main tree by construction — the same call is right in every checkout and there is no branch to get wrong.

**One writer, three appetites, and the difference is who asked.** `scripts/launch-config.py` holds the shape; the Makefile target FORCES because somebody typed it, the hook passes `--if-needed` because it runs unasked, and `make status` passes `--check` and writes nothing. Splitting the appetites rather than the writers is what stops the two from drifting, which is the failure this entry is otherwise entirely about.

**It rewrites an absent or a stale file and never a hand-edited one.** Stale is the narrow case — this repo's exact shape at the wrong port, which is precisely what the Browser pane's template produces. A second configuration, a different command, a `url`, JSON that does not parse: all reported, none touched. That asymmetry is **D44's**, taken deliberately rather than reinvented — `make icloud-sweep` deletes only what is provably a duplicate and only ever reports what differs, on the grounds that guessing is the one way a cleanup tool destroys work. Something that runs on every session start without being asked has more reason to keep that rule, not less.

**`make status` reports a disagreement, because the hook fails open by design.** That is this repo's standing rule for hooks and it is right, and its cost is that a skipped hook is silent. The status line closes exactly that gap: it is the surface whose whole job is saying what state you are actually in, it already reports NOT ARMED for the git hooks on the same argument, and it is silent when the two agree so the ordinary case costs no line.

**What is still not closed**: a worktree gets the fixed hook only once this lands on the branch it was cut from. The guard is a tracked file, so a tree cut from an older main runs the older guard and goes on needing `make launch-config` by hand. Nothing can reach backwards into a checkout that does not have the code.

### And a second file decided whether a worktree could write at all

`server/capture_server.py:DEFAULT_ALLOWED_ORIGINS` was the literal tuple `("http://localhost:5173", "http://127.0.0.1:5173")` — the CSRF allowlist naming the only origins permitted to POST, PUT or DELETE. This entry moved the dev port itself, `vite.config.ts`, `playwright.config.ts`, `app/src/server.ts` and eventually `.claude/launch.json` onto one derivation, and left the allowlist on the constant.

**So a linked worktree served an app whose every write its own server then refused.** The app comes off that tree's derived dev port, the gate expects 5173, and the answer is 403 `origin_not_allowed`. Observed on the worktree at `.claude/worktrees/inventory-delete-feedback-2b96fa`: capture, undo, mark-sold, retire, the mid-box delete and the claim editor all refused. **Reads are ungated**, so every screen rendered, the inventory drew, the walk worked — a branch's app could look at its store and never change it, and the only way to find out was to press something. `PKMNSCAN_ALLOWED_ORIGINS` was the workaround and nothing pointed at it until the refusal arrived.

**It is this entry's own rule with one more reader, and that is the finding rather than the fix.** The paragraph above says it about `launch.json` in as many words — a tracked constant cannot be right in every checkout — and the same sentence was true of a second file nobody had enumerated. What both misses have in common is that they are readers of the port that are not *servers* on it: the bind moved because it was obviously about the port, and a launch config and an origin allowlist are about the port without looking like it.

**`ports.dev_port()` is asked once, at import.** Unlike `allowed_origins()` one line below, which is read fresh per request because its input is an environment variable a running server should pick up without a restart, this has no input that can change while the process lives.

**Nothing moves in the main tree**, which is the property that makes this safe and also the reason it hid: `dev_port()` answers 5173 there by construction, so the tuple is byte-identical to the constant it replaces wherever the owner actually works, and every doc naming that number stays true. Only a linked worktree changes, and only from *refuses everything* to *allows its own app*.

**A checkout allows its own origin and not the main tree's.** Adding 5173 back for worktrees was the obvious way to be generous and is the wrong one: it would let a page served by the MAIN checkout write into a branch's store, which is the cross-tree write this entry exists to prevent, arriving through the one control in this repo whose job is to stop a page writing where it should not. Pointing one tree's app at another tree's server is a real thing to want and is already deliberate — `VITE_CAPTURE_SERVER` — so it takes the deliberate answer, `PKMNSCAN_ALLOWED_ORIGINS`.

**Covered in `check_origin_gate`, which had the constant written into it too.** That block asserted `["http://127.0.0.1:5173", "http://localhost:5173"]` literally, so it would have gone red in a worktree for the right reason and green in the main tree for the wrong one. It now asserts the PROPERTY — both spellings, at the port this checkout's app is actually served on — plus that a non-worktree root still derives 5173, and, in a worktree only, that the main tree's origin is NOT in the list. Mutation-tested: restoring the constant takes two of them red.

**The honest limit, named because it is how the defect survived: none of those cases can fail in the main checkout.** 5173 is correct there whichever way the list is built, so the whole guard is only ever exercised by somebody running the harness from a worktree — which `make worktree-setup` and the Stop hook make ordinary, and is why the case is worth having at all. The block says so in a note rather than leaving a green run to be misread.

---

## D44 — an iCloud conflict copy is refused at the commit and never deleted on a guess

**Built 2026-08-29, and it is a decision about an ENVIRONMENT rather than about the product.** This repo lived in iCloud Drive until later the same day (see the amendment at the foot of this entry). iCloud resolves a same-file race by writing a second file beside the original with `" 2"` appended to the stem — `pre-push 2`, `githooks-selftest 2.sh`. Three appeared in one afternoon. The owner was moving the repo off iCloud; this entry is what held until they did, and it costs nothing afterwards.

**It had already done damage twice before anything guarded it.** `make hooks` copied `scripts/githooks/*` and installed **five hooks from three files**, two of them untracked and reviewed by nobody — git dispatches on exact names so it would not have run them, but the mechanism put unreviewed code into the hook directory. And `githooks-selftest 2.sh` failed a commit on the repo-map orphan rule, which is the *good* outcome and only happens inside a mapped directory with a declared suffix.

**The third failure is the one worth recording, because it is not about file names at all.** An in-place overwrite of `server/ports.py` left iCloud serving **stale bytes to Python's import machinery**: in one interpreter, `open(path).read()` returned the new file and `import` ran the old one, with no `__pycache__` present and `-B` set. A test that had just been mutated read as passing against code that was no longer on disk. The mitigation is a same-directory stage plus `os.replace` — a rename swaps the inode and cannot be served stale — and it is why `scripts/status.py`'s helper preserves mode as well, having dropped `+x` from a SessionStart hook on its first outing.

**Three responses, graded by how sure we can be:**

- **`make hooks` installs only what `git ls-files` returns.** Not a guess — a hook directory whose contents are decided by what is lying on disk has given up the reviewability that is the reason those files are tracked at all.
- **The pre-commit hook REFUSES a staged conflict copy.** They are untracked, so they are invisible until something says `git add -A`, which is exactly what an agent session says. A committed `foo 2.py` is a second copy of a module no import reaches and no test runs, read later as a file somebody meant to write. `PKMNSCAN_DUPES=off` is the bypass, for the deliberate `Section 2.md` nothing in this repo has yet needed.
- **`make icloud-sweep` deletes ONLY a copy that is byte-identical to its original**, and reports every differing one without touching it. That asymmetry is the whole design. Identical means iCloud copied a file that still exists unchanged, so there is nothing in it to lose. Differing means it is not provably a duplicate — it may be the newer of two real edits, and this script cannot know which. Guessing there would be the one way a cleanup tool destroys work.

**IT IS NOT IN `make check` AND NOT IN THE GIT HOOK.** D18 at its strongest: it is the only target in this repo that can delete a file. It is also not a defect to *have* conflict copies — the commit path already refuses them — so failing `check` would gate a tidy-up on something the filesystem creates on its own schedule. `make status` reports the count, which is where a fact you should know but need not act on belongs, and is silent when there are none.

**What retires this: leaving iCloud Drive.** The sweep then finds nothing forever, the pre-commit rule costs one grep per commit, and the `git ls-files` enumeration in `make hooks` is correct on its own terms and stays regardless.

**That condition fired on 2026-08-29. The repo is at `~/Developer/pkmnscan` and nothing in this entry is deleted.** The paragraph above is the whole disposition and it was written to be executed rather than re-argued: `make icloud-sweep` reports `no conflict copies` and will go on doing so, the pre-commit rule is one grep, and `make hooks` enumerating `git ls-files` was never about iCloud in the first place. So all three stay armed.

**Kept rather than retired, and the distinction is what this amendment is for.** A guard that costs a grep is not worth the argument it takes to remove, and the hazard is a property of a DIRECTORY rather than of this project — the repo could move back, a checkout could be made inside a synced folder on another machine, and the same `foo 2.py` would appear with nothing watching for it. What IS retired is the urgency: this entry no longer describes the environment the work happens in, and a session reading it should treat the three failures below as an account of what the guards were built from rather than as conditions live today.

**The one thing that genuinely ends is the stale-import hazard**, because it was never about file names: `os.replace` in `scripts/status.py`'s helper is correct on its own terms and stays, but the failure it mitigates — iCloud serving an interpreter bytes that are no longer on disk — cannot happen in a directory nothing syncs.

---

## D45 — The copies list is a way back into the walk, and the filter yields to the jump

**A copy's position label is a control: pressing it walks the box browse to that copy, switching box if it has to.** Built 2026-08-29, from the owner asking whether clicking a copy in the preview could redirect them to that copy's photo — a backroad way of getting around.

**D7's map was a read-only answer, and that is the whole of what this changes.** Every copy of a card sits at its own position and `CardLocations` has drawn them since the order flow — three copies, three boxes, three position labels — with no way to get to any of them but reading the box number off the row and pressing that cell on the strip. The walk already draws the photograph, the facts, the queue block and the box operations for whatever it points at, so moving the mark is the ONLY thing a press has to do; everything the owner asked for follows for free.

**The label is the control and the row is not.** The row already holds `Mark sold` and the retire door, and a button inside a button is invalid markup — the same constraint that put `aria-current` on the `<li>` rather than on anything pressable. The label is also the better target on its own terms: `Box 7 · Section 1 · Card 40` is both the affordance and the statement of where the press is about to go. It renders through the identical class in both branches, so a walkable row is not louder than a look-only one; what the button adds is `cursor`, an underline on hover and focus, and `Walk to <position>` as its accessible name.

**It is absent on the current copy and on a pooled one.** The first is where the walk already stands. The second is D24: a code card is a count rather than a location, so there is no slot to walk to and that cell is carrying the pooled fact instead of a position.

**`BoxBrowse` gains one inbound prop, which is the mirror of `onSelect`.** `goTo: { key, at }`. The two shapes declined: an imperative ref handle, which hides a state change inside a method call; and lifting `selected` into `Inventory.tsx`, which hands a page the walk's own bookkeeping — the four effects that keep the mark inside the filter, the shelf and the fold. The counter is there because the same copy can be asked for twice — walk to it, arrow away, press it again — and because a request already answered must not be replayed by a re-render of the caller.

### The filter is the failure this entry is mostly about

Under a query the walk holds only matches, and the two follows-the-filter effects move the mark to the first visible row whenever the selection is not among them. So a jump to a card the query does not reach lands on **whatever card is first**, under its own photograph, with nothing on screen saying the wrong one was reached. Observed, by removing the guard and running the case: pressing `Walk to Box 7 · Section 1 · Card 40` drew `Box 2 · Section 1 · Card 1`.

**It is reachable for one reason and the reason is worth keeping.** `do_search` renders a SKU's group WHOLE — every copy, including ones that did not match the query — so a copy of a matched SKU is always inside the walk's own filter. **The `sku: null` group is the exception**: it is built from the cards that matched THEMSELVES, and a named, never-emitted card is most of this store today. Two copies of one name in two boxes and a query that reached only one of them is the live case.

**So the query is dropped rather than the jump.** The owner pressed a position; the filter was a way of finding it, and it has been found. Clearing re-runs the landing with the whole walk to land in, which is why the request is held in state rather than answered in one pass.

**The jump opens the landing's section itself**, and that is not what the mark-is-never-hidden rule already does. That effect runs a commit later and the scroll's dependencies do not include the folds, so a jump that left the opening to it lands on a row the scroller never scrolls to. Measured on a forty-card box: viewport ratio 0. The landing effect is declared AFTER both fold effects for the same class of reason — clearing a query fires the collapse-everything effect in the same pass, and last means the open is the final word.

**What it costs is the ticks, named rather than designed away.** A shelf change clears the mass-select (D31: the selection is box-scoped because the write it feeds is), so walking to a copy in another box discards a selection that may have been on its way to `#/runs` via D39's handoff. It is the same cost a box-chip press already carries; what is new is that the gesture looks like a click on a row rather than a click on a box. The mitigation is the control itself — the thing pressed prints the box it is going to.

**A key the walk does not hold does nothing.** The copies come from `GET /search` on every selection and the walk from `GET /inventory` at mount, so a card deleted from another device sits in one and not the other until a Reload. Naming it would need a refusal channel out of a component that reports three things upward and takes one back; the press doing nothing, with the Reload beside the list as the remedy, is the honest cheap answer.

**It does not reach the Fulfiller**, and that is D31's downstream rule rather than an omission. `onGoTo` is optional and owner-skin only; his view has no walk to move. The gallery passes nothing. The lone-copy fallback passes nothing either — that copy IS the card the walk is standing on.

### A premise that expired between writing and merging

This paragraph was written against a premise that no longer existed by the time it merged, and the correction is the useful part. It read that D41 IS UNTOUCHED — that entry ruling the three sites drawing `Position.label` are decided one at a time, and this changing none of them, since `.card-locations-label` renders the same string through the same class at the same size. Both halves went stale in the hours this branch was out: D41's amendment took the treatment to **six** owner sites behind `app/src/PositionLabel.tsx`, and the copies list is one of them — so `.card-locations-label` carries the SITE rule (`--pos-slot`, the face, the color) and renders none of the string itself. Left standing it would have been D41's own recorded failure repeating in the entry that cites it: a later change deleting the premise and leaving the conclusion.

**What is true instead is a stronger property than the one claimed.** The walk-to is a TRANSPARENT WRAPPER around `PositionLabel` — same three props, no text of its own, the site's font and `--pos-slot` inherited through it — so a walkable row and a look-only one are the same pixels, and the copies list does not become a seventh site by acquiring a control. The one thing the wrapper adds is hover and focus, and it is scoped to `.position-slot`, the anchor that component already chooses, so it cannot reach the five sites that offer no walk-to. `pipeline/join.py:Position` still composes the string and it still travels verbatim on `aria-label`; the button's own name says what pressing it does.

**What would reopen this: the same affordance asked for elsewhere.** If walking to a position becomes how the owner navigates generally, `#/review`'s position is the next site — and it is now a decision about a shared component rather than about three copies of a treatment, which makes it cheaper to take and easier to take carelessly. **The Fulfiller is not on that list at all**: `PositionLabel`'s own header records that his screens never import it, `app/tests/fulfillment.spec.ts` floors his position at >=32px plain, and D31 keeps that spec unweakened.

### The jump scrolled the page rather than the walk

The owner, 2026-08-29: picking from a copy of a card moved the screen down to where it hid the top bars. The landing effect ends by scrolling the landed row into view, and it did that with `Element.scrollIntoView` — an API that scrolls EVERY scrollable ancestor, the document included.

**On a sticky column that moves the page without moving the row**, which is why the press cost something and bought nothing. `.browse-map` is `position: sticky`, so a row inside it does not change its viewport position when the document scrolls; the browser computes a delta from the row's current geometry all the same, spends it on the page, and the row stays exactly where it was. Measured at 1280x720 with the page at rest: **`window.scrollY` 0 -> 280, the document's whole range**, putting the nav at y=-280 and this screen's own header at y=-218. The landing was already going to be visible — the walk's own scroller had done that work — so the entire effect of the page scroll was losing the nav, the title row, the search field and the box strip.

**The fix is a ceiling, not a flag: `BoxBrowse.tsx:scrollWithin`.** It adjusts `scrollTop` by hand on each scrollable ancestor from the row up to `.browse-map` inclusive and stops, so the document scroller is unreachable **by construction**. `scroll-margin-top` is read off the row rather than ignored, because `.browse-row` sets 28px to clear its own sticky section header and a hand-rolled scroll that dropped it would park every landing underneath that header. The innermost scroller takes `start` and every outer one takes `nearest`: `start` is a statement about where the row sits in the LIST, and asking the same of the column outside it would drag the search field and the box strip off the top of a column that is only ever scrolled to reach the box's editors.

**The ceiling holds with the boundary missing**, and that is a separate line rather than a null check. The walk stops at `document.body`/`documentElement` before it consults the boundary at all, so a ref that has not mounted yet cannot let the walk past — a ceiling that depends on a ref being non-null is not a ceiling, and the symptom would have reappeared nowhere near the check that failed.

**It reaches every gesture that moves the mark**, not just the walk-to, because they all land in one effect: arrow keys, PageUp/PageDown, Home/End, a box-chip press and a search landing. Verified against the owner's own store — a walk-to across 133 real cards moves `.browse-list` 1242px and the page zero, and a box-chip press from y=5 leaves the page at y=5.

**`focus()` is the same defect's second door and is shut with it.** Two presses hand the keys to the walk, and `HTMLElement.focus()` scrolls the focused element into view by default — the document included. Measured, neither fires today: the column is sticky at the top of the viewport, so the list it holds is already on screen whenever these run. Latent rather than live, closed for one object, and recorded here so it is not read as belt and braces: `scrollWithin` owns where this component scrolls and nothing else in it may.

**A comment that argued for the defect is corrected rather than deleted.** The landing effect ended by saying the page scroll this brings with it is wanted here, because the copies list is below the card band and the photograph is what was asked for. The intention was right and what happened was its opposite — the scroll came from the landed ROW, so it moved the page DOWN, away from the card band. Kept in the file with that account attached, because a comment that reasons its way to the wrong behavior is more useful than a missing one.

**Asserted as a MEASUREMENT rather than as a class name**: `app/tests/inventory.spec.ts` reads `window.scrollY` and the nav's own `top` before and after the press and requires both unchanged, AND requires the landed row in the viewport — either alone is satisfiable by doing the wrong thing, since a screen that scrolled nothing and landed nowhere would pass the first and the old code passed the second. Observed red against `scrollIntoView` before it was kept.

**One trap on the way, worth keeping because it wasted the first attempt.** Playwright's own `.click()` scrolls its target into view first, so the first version of this measurement read 280 both before and after and proved nothing. The case dispatches the press instead.

---

## D46 — A card the pipeline could not place is offered the catalog, and a human may point at a row

**Built 2026-08-29, and the owner found it from the far end.** Shown three cards rescued by D35's name rung, they asked why the fourth was still a dead end and why the screen said nothing useful about it: *"it should've brought up what cards it could have matched too (along with letting me literally just enter in what it is)"*.

**The dead end was real and it was total.** A queue entry with no candidate rows cannot be answered — `POST /review/<box>/<index>/answer` refuses it as `no_candidates` — so the only two moves were Skip, which writes nothing and asks the same question next session forever, and D37's stand-down, which closes the question rather than answering it. Neither one lists the card. The row was in the export the whole time.

**The case that reopened it is the one the old refusal said did not exist.** That refusal argued from evidence and named it: *"Every one of them wanted a re-export or a re-shoot, never a typed SKU, so the refusal stands on the evidence it asked for."* True of the cards it was written about. Box 1 position 108 is not one of them. Its photograph is **good** — measured at 2160x3840 with mean luma 72.2, statistically indistinguishable from two copies of the same card that read perfectly — and `Master Yi, Wuju Master` came back as `Wuju Master`, the champion dropped. A re-shoot repairs nothing, a re-identify is a coin toss, and a person looking at the card can see what it is.

**It is not a free-text path into the field the hard rule protects, and that is the whole design.** The operator never types a SKU into a card. They pick a ROW, and the server re-reads that row **out of the export this card was joined against, inside the write lock**, before anything is written:

- an unknown SKU refuses as `sku_not_in_catalog`;
- the **condition is taken from the row, never from the request** — a client that sends the wrong one gets the right one rather than an error, so the SKU is the only thing the request decides;
- and `from_catalog` reaches only an entry with **zero** candidates. An entry with rows of its own still answers only from those rows, so the anti-laundering refusal is untouched.

The property the old guard protected — that no string a client sends can become a listing on its own — is therefore unchanged. What changed is that a human may point at a row the pipeline failed to find, instead of only being able to walk away from it.

**The edge is on the card, not on the queue entry, and that is what makes the lookup exact.** `store/queues.py:QueueEntry` records no run, no game and no export, and `Queue.parse` drops any key it does not declare — so nothing about a run can be written into `review.json` without a schema change. `master.Card` has carried `run` since identification wrote it and `game` since D21, and the answer path already loads the card. So: card -> run -> that run's manifest -> the export for that card's game. Guessing the run by scanning `runs/` for one whose scope covers the box was the alternative and it is **unsound**: two runs on this machine touch box 1, `first_seen` is date-only, and `Queue.upsert` preserves it across re-joins. An exact edge that is sometimes absent beats an inferred one that is always present and sometimes wrong. Every way it can be absent is a named refusal — `no_run_recorded`, `run_not_found`, `no_export_for_game`, and `export_missing`, which is the legacy case: a join driven from a terminal records the `--export` path it was handed, typically `~/Downloads/...` and often gone, while a join driven from the app uploads the bytes into the run.

**The match is loose in both directions and is allowed to be, because it decides nothing.** `CLAUDE.md` forbids the JOIN to match on Product Name, and that stands — this is not the join. It ranks rows for a person to choose between, so a loose match costs a row on a list rather than a wrong card in an import file. Measured on that export: **490 of 494 epithets identify exactly one product, against 38 of 98 champion names**, and the same run truncated in both directions (`Wuju Master` three times, `Master Yi` twice). So both directions are offered and neither is trusted without a human looking at the photograph.

**The rows go where the candidate rows go, and are answered on the same digits.** Not a panel below them: `ReviewQueue.css` holds that nothing may come between the sentence and the rows, and these ARE the rows — found by a lookup rather than by the join, drawn through the same markup. One vocabulary rather than two, because whether the pipeline or the catalog found a row is not something the finger needs to know. The search box is a form, so Enter submits it, and `isEditableTarget` is what stops a typed `1` from answering the card — asserted as a negative case, because nothing in the type system says so.

**The history line carries `from_catalog`, and only when it is true.** `_history` drops a None extra, so every line already on disk keeps its exact shape. A row the PIPELINE offered and a row a HUMAN went and found are different claims about how much the machine knew, and after the write there is no other evidence which happened.

**The stale copy went with it.** That arm drew one paragraph saying the only move was to skip and pointing at a command in a terminal. D37 had put a stand-down on this very screen months earlier and the copy never mentioned it — the one place that most needed to.

**What would reopen this: the flag being used on cards that had a good answer available.** If `from_catalog` starts appearing on answers for cards whose export row a better join would have found, the fix is upstream in the join, not more catalog searching. `_repair_set_code` is the first instance of exactly that: three of box 1's four dead ends turned out to be a set code glued to a correct identifier, and code now recovers them without a human at all. **It was `_strip_set_code` and a two-character rule until 2026-08-30, when box 3 produced the same defect across three separators at 7 of 39 — D55 is that amendment**, and it is also this paragraph's own rule pointing the other way: the repair keeps working and the READ is what has not improved.
## D47 — A tracked symlink is a path baked into the tree, and a checkout will spend a directory to place one

**A symlink that leaves the repository may not be committed, because checking it out elsewhere destroys whatever stands in its way.** Built 2026-08-30, after a `git merge --ff-only origin/main` in the main working tree replaced the 133 MB eval-image mirror with a link pointing at itself. No file was written by hand and no script misbehaved: the checkout did exactly what it was told, and what it was told was wrong.

**The data came back, and the entry is written as though it had not.** iCloud Drive restored the directory from its own copy about ten minutes later — 150 images and the manifest, intact — and removed the empty conflict copy it had made in the meantime. That is luck wearing the clothes of a backup: the same sync layer D44 exists to defend against is what happened to be holding the only other copy. On a machine without it the loss is permanent, and the remedy would have been a 151-file re-download rather than nothing at all only because D15 makes this data derived. **The first draft said the mirror was deleted, because that was true of every observation available for ten minutes.** Corrected rather than quietly softened, because the mechanism is unchanged by the recovery and is the reason the rules below exist.

### The mechanism

`scripts/worktree-guard.sh` provisions a linked worktree by symlinking two gitignored things to the main tree — `app/node_modules` and `harness/images`. Correct there, and necessarily an **absolute path**. Then:

1. `.gitignore` said `node_modules/` and `harness/images/`. **A pattern ending in `/` matches directories only**, and git does not count a symlink as a directory — so neither link was ignored in a worktree, and both were invisible to a reader who had just read the ignore file and concluded they were covered.
2. A session ran `git add -A` and committed both, as mode `120000` blobs whose contents are an **absolute path on one Mac** — the main working tree's own location, followed by the same two names.
3. In the **main** working tree those paths name the links' own locations. Checking the commit out there makes each one a symlink to itself, and **git removes an ignored file or directory that stands in the way of a checkout without asking**. The real directories were ignored, so they were removed.

**What it cost, measured.** `harness/images` — 133 MB, 150 eval images and the manifest that labels them — was replaced by a self-referential link at 20:13 on 2026-08-29, with an empty iCloud conflict copy (`harness/images 2`) beside it. Every worktree linking to that path went dangling with it. T1 failed with a `FileExistsError` from `IMAGES_DIR.mkdir(exist_ok=True)`, which is what `mkdir` does when the path exists and is not a directory: **the error names the symptom and says nothing about the cause**, which is why this took a full investigation rather than a glance.

**`app/node_modules` was in the same trap and survived by accident.** The pull that detonated the images also carried a commit that had removed the node_modules entry from the index — for an unrelated reason, while cleaning a merge — so the add and the delete cancelled and git left the real directory alone. An accident is not a guard, and this entry is what replaces it.

### The fix is three things, and only the third is new machinery

- **`harness/images` is untracked.** It was the only tracked symlink left in the tree.
- **Both ignore patterns lose the trailing slash** — `node_modules` and `harness/images` — so they match a link as well as a directory. That is the one-character fault at the root of it, now stated in the file with the reason attached.
- **The pre-commit hook refuses a staged symlink that leaves the repository.** It reads mode `120000` out of the index rather than guessing from a name; an absolute target is refused outright, and a relative one is refused when it climbs out of the tree. **A relative link that stays inside is allowed**, because that is the only kind that survives a clone on another machine — which is the property actually being enforced. `PKMNSCAN_LINKS=off` bypasses, in the shape the iCloud-duplicate rule beside it already uses.

### The mirror left iCloud and came back

**Moving it out was the owner's call and not a consequence of the bug.** `PKMNSCAN_IMAGE_MIRROR` had been documented since build-order step 9 and read by nothing; `harness/eval/fixtures.py` honors it now, and the allowlist entry that carried it as a documented-but-unbuilt name is retired the moment it came true, exactly as D16 requires. The default is unchanged, so a tree that sets nothing behaves as it always did and every banked score stays comparable. The reason for moving it was D44's: this repository sat in iCloud Drive, and 133 MB of derived binaries syncing there is what produced the conflict copies that entry refuses.

**And moving it gives up the thing that just saved the mirror**, which is the honest way to record the trade. iCloud's copy is what restored the directory. Outside it there is no second copy and no version history — the recovery path becomes the re-download, which is exactly what D15 says this data is for: derived, reproducible, and never the artifact worth keeping. A safety net that costs conflict copies, against a clean tree whose worst case is one download. The owner took the second.

**The mirror came home on 2026-08-29, hours after it left, because the repo left iCloud and took the whole reason with it.** `PKMNSCAN_IMAGE_MIRROR` is unset, `harness/eval/fixtures.py` falls back to its own default, and the 152 files sit at `harness/images` where every version of this project before 2026-08-30 expected them. Measured after the move: `IMAGES_DIR` resolves in-repo, 152 entries with the manifest, `make harness` all 7 passed, `make ignore-check` green.

**Both paragraphs above are void as dispositions and kept as reasoning, and the second is why this was cheap to reverse.** The trade it records had exactly one term on each side, and leaving iCloud zeroed both at once. There are no conflict copies to pay because nothing syncs the directory, and there is no safety net to give up because there was none left to lose. A decision whose two arguments both evaporate is not one that has to be re-argued; it is one whose premise is gone, and the honest move is to put the data back where the default already pointed.

**What survives, named so nothing is unpicked with it.** Three things landed under this heading and only one was about iCloud:

- **The knob stays and is still honored.** D15 authored `PKMNSCAN_IMAGE_MIRROR` for the mirror's SIZE, not its sync status, and ~16.7 GB at full catalog is still the reason which disk it lands on is a choice worth having. Unset is not unbuilt: the code reads it, the allowlist entry stays retired, and a tree that wants the mirror elsewhere sets one line.
- **The provisioner still ASKS rather than assumes.** `scripts/worktree-guard.sh` running the main checkout's `fixtures.py` to learn where the mirror is was written because the move broke it, and it is correct whatever the answer — including today's, which is the in-repo default it used to hardcode. Reverting it would restore the silent skip, not the old code.
- **`harness/images` keeps its type-agnostic ignore pattern.** That is this entry's own subject and has nothing to do with where the bytes live: the pattern exists so a worktree's SYMLINK at that name is ignored, which is the fault this entry opens with. A directory there now makes the pattern matter more, not less.

**What would reopen this: the repo going back into a synced folder.** Then D44's hazard returns and the mirror is the largest thing in the tree that would sync, so moving it out is the first remedy to reach for — and it is one line in `.env`, which is the whole point of leaving the knob alone.

**What this does not do.** It does not stop `worktree-guard.sh` making the links — they are right, and they are what keep T1 from re-downloading 151 files per worktree. It does not make symlinks a bad idea. It stops one of them being **committed**, which is the only step in the chain where a local convenience becomes every checkout's problem.

### It broke the audit on its way in, and that defect was older than this entry

Writing the paragraphs above put the string `app/node_modules` into a doc, which made it a path candidate — and `scripts/docs-audit.py:ignored_paths` probes missing candidates through `git check-ignore --stdin`, which **exits 128 and stops** on a pathspec it refuses. A provisioning symlink is exactly such a pathspec, so the batch aborted and every candidate after it lost its answer. The audit then blocked the commit over `harness/.cache/` in `docs/GATES.md` — a reference that was correct, unchanged, and in a different file.

**A batch that did not run cleanly is not evidence about anything.** check-ignore's contract is 0 when something matched and 1 when nothing did; any other code means it gave up. It now falls back to asking one candidate at a time so a refusal is contained. The failure mode this replaces is the worse kind: not a check that misses something, but one that **reports a defect in a file nobody touched**, which sends a session investigating the wrong doc.

### Moving the mirror broke the provisioner, and the provisioner said nothing

Found 2026-08-30 by a Stop hook that failed T1 in a worktree whose main checkout was healthy. This entry moved the mirror behind `PKMNSCAN_IMAGE_MIRROR` and did not look at the one script whose job is to give a worktree that mirror. `scripts/worktree-guard.sh` and `make worktree-setup` both read `[ -d "$main/harness/images" ]` and linked THAT path — and after the move the main checkout has no `harness/images` at all, so the precondition went false and both blocks were skipped whole. **Neither printed anything**: the only failure message sat on the `ln`, and the `ln` was never reached. A fresh worktree then downloaded 151 images at its first `make harness`, which is the exact cost the guard's own header says that line exists to avoid.

**The fix is to ask rather than to assume, and the thing asked is the one resolution.** Both call sites now run the MAIN checkout's own `harness/eval/fixtures.py` and link to whatever `IMAGES_DIR` answers — env var, then that checkout's `.env`, then its in-repo default. Re-deriving that precedence in shell is how the two drift apart a second time, and `fixtures.py` is stdlib-only at module scope so a bare `python3` can answer it. The script never reads `.env` itself; `envfile` does, and the only thing crossing the pipe is a path. Where there is no mirror to link, it now SAYS so — the silent skip was the defect, not the missing link.

**That resolution answers `harness/images` again as of 2026-08-29**, the mirror having come home. The fix is untouched by that and must stay: what it replaced was a hardcoded path that happened to be right, and it is exactly as wrong to hardcode a path that happens to be right today.

**And the path belongs in `.env`, not in a shell profile.** Tried and reverted the same day: an export in `~/.zshenv` fixes an interactive session and does nothing for the Stop hook, which runs `scripts/stop-gate.sh` under **bash** — a shell that reads no zsh profile and, spawned from an app started before the export existed, inherits nothing either. `.env` is what every reader of this repo already consults regardless of shell, and `envfile.get` still lets a real environment variable win. Two records of one path is also drift this file dislikes: a stale export would outrank a corrected `.env` and point at a mirror that had moved.

### The reverse direction, closed the same day

**What would reopen this: a third provisioned path.** The guard is general — it refuses by mode and by target, not by name — so a new link is covered the day it is added. What was not covered is the reverse: a path that ought to be ignored and is not, which is what let the first one through. `git check-ignore` over the provisioned set, run off the commit path, would close that half.

**It reopened the same day, by exactly that direction.** Two of the four provisioned paths kept their directory-only patterns — `harness/.cache/` and `.venv/` — on the reasoning that `scripts/worktree-guard.sh` COPIES the first and BUILDS the second, so neither is ever a link. That reasoning is sound about the script and says nothing about the path. A session that provisioned a worktree by hand linked both, and got this entry's own state straight back: **untracked rather than ignored**, one `git add -A` from committing an absolute path into one Mac.

**It also broke something this entry did not predict.** `scripts/docs-audit.py`'s ignore filter exists so a gitignored path is not reported as a dangling reference — and it had nothing to match, so every doc reference to `harness/.cache/` read as a broken path and the pre-commit hook blocked a commit over two of them. That is the audit being right for the wrong reason: the reference was fine and the ignore was not.

**So the rule is about the PATH and not about today's provisioning.** All four patterns are type-agnostic now. The precision a trailing slash buys is worth nothing on a name nothing else in the tree bears, and it is worth less than nothing when it silently depends on a script's current behavior staying what it is.

**And `make ignore-check` is the guard this entry asked for**, doing exactly what the paragraph above specified: `git check-ignore` over the provisioned set, asserting each is ignored **as a file, as a directory and as a symlink**. It is in `make check` and deliberately NOT in the git hook — D18's rule, and a second reason of its own: what it checks is a property of the local worktree's provisioning, so a fresh clone with none of these paths present would fail a commit over something that is not wrong. Off the commit path is where a check about local state belongs.

---

## D48 — A send is a cart of boxes; a run is still one box

**One send may carry several boxes, and each box still gets its own run.** Built 2026-08-29 on the owner's instruction after being told what the pipeline could and could not already do: they wanted to multi-select and have them all send at one time, and then — when the first answer proposed one run spanning several boxes — asked why the bypasses could not be per box, joining a queue to Haiku with a further button that batch-sends all the individualized boxes at once.

**The owner's shape was better than the one proposed to them, and the correction is the useful part.** The first recommendation was ONE RUN over several boxes, on the argument that `join` already reasons per box (D36's realign does), that `sidecar.scan` already parses `box3-0017.jpg`, and that emit aggregating across boxes gives one import file per game instead of several. Every one of those facts is true and none of them is the deciding one. What decides it is that a run carries a **reading**, a `--bypass` ruling and a `decisions.json`, and all three are properties of what is IN the drawer — so one run across three boxes forces one answer to three questions that deserve three. The owner's word for it was *individualized*, and it is the right one.

**So the cart is the request and the run is unchanged.** `POST /pipeline/identify` takes `scopes: [{box, indices?, crop?, max_edge?}, ...]` and spawns one detached child per box. Every box gets its own run directory, its own manifest scope, its own queue, its own join and its own pricing answer. Nothing downstream learns a new shape, and that is the property worth protecting: `cli/runs.py`, `join`, `emit` and `reconcile` were not touched by this entry at all.

**One route still spends, with one `confirm` and one total.** Two alternatives were declined for the same reason. A second route beside the first would double the surface D33 spent a whole entry putting behind one door. N calls from the screen would be N confirms for one operator decision, which is the two-step money gate satisfied in letter and broken in substance. One press, one request, one `confirm`, one estimate on screen above it.

**The total is summed on the server, and a missing figure poisons its sum.** `app/src/server.ts` already records that the app may not compute rules the pipeline owns, and this is the sharpest case: the total is the number the operator agrees to spend. `_parse_preflight` answers `None` where a line did not appear — deliberately, so a changed preflight shows as a missing figure rather than a confident zero — and a sum that skipped a `None` would undo that at the one moment it matters, by understating what a press is about to buy.

**A bare `box` reads as a cart of one, and nothing ever writes one.** The read-side widening D3's amendment gives the finish claim and D21 gives `game`, for the same reason and with the same boundary: the harness, a terminal, and every request written before today resolve down the identical path with no migration and no second spelling on the wire. The RESPONSE is always a list too — a shape that changed with the request would make every reader ask which one it got before it could ask anything else.

**Every leg is resolved before any is acted on, and a refusal tears down what it built.** D29's validate-everything-then-write-everything with an invoice instead of a queue answer: a bad flag on the fourth box refuses the whole send rather than leaving three boxes identifying. Because `_resolve_scope` creates a symlink directory per ticked selection, a refusal also removes the ones earlier legs had already made — T7 asserts, in as many words, that no scope directory survives a refusal, and a cart could otherwise leave one per mis-typed send in the one directory `identify` walks recursively.

**The one thing that cannot be pre-checked is reported rather than hidden.** `Popen` can fail on the fourth leg after three have started. The response names what STARTED and what did not, and the screen draws the failures: a partial send reported honestly is recoverable by pressing again for the boxes that did not go, and one reported as a success is an invoice nobody can account for. Recorded here because the tempting alternative — refusing the whole response — would throw away the names of runs that are already costing money.

**The double-click guard now compares boxes, which closed a hole that had no guard at all.** `_busy_run` resolved the incoming capture directory against each live run's recorded one. That works for a whole box — `captures/cards/box3` both times — and cannot work for a ticked selection, because `_scope_dir` builds a fresh `.scopes/box3-<n>-<timestamp>` on every press. Two presses over one selection were two different paths, neither saw the other, and **the subset path was therefore unguarded from the day it was built**. It compares box numbers now, read from the manifest's scope first and from the capture directory's name second — and the second half is not a fallback for old files, it is the only thing that can see a run started in a TERMINAL, because `scope` is written by the route and by nothing else.

**It narrows what is allowed, deliberately.** Two live runs over DISJOINT selections in one box are now refused as well. That is the case an operator cannot tell apart from a double-click at the moment of the press, and the refusal names the run, so the answer is one click away rather than one invoice away. Two runs over DIFFERENT boxes stay legal and unblocked — the Batch API takes them in parallel and the cache keys them apart, which is the whole reason a cart is one send rather than a queue.

**The legs preflight at once, and that is a latency fix rather than an optimization.** A preflight decodes and crops every photograph in its box — measured at about a minute for 544 cards — so five boxes in series is a request held open for five minutes with nothing on screen. They are separate read-only processes over a lock-free snapshot and `--dry-run` writes nothing at all, which is the property that makes this safe rather than merely fast. Bounded at four workers, and the cart itself at sixteen boxes: each leg is a detached child, so an unbounded list is an unbounded number of processes started by one request. The bound is a guard against a malformed client, not a judgement about how many boxes an operator may send.

**D39's handoff rule is narrowed rather than weakened.** That entry drops the ticked selection whenever a box is picked on `#/runs`, because a tick list that survived the operator deliberately choosing a box is a filter they did not re-consent to, sitting over the control that spends. Under a single-select every press REPLACED the scope, so every press was a re-consent question. Adding box 7 to a cart does not touch what box 3 means, so the rule now scopes to the carried box: un-ticking it drops the handoff, and toggling any other box leaves it alone. There is still exactly one mass-select in the product and `#/inventory` still owns it.

**A defect was found in the run list on the way past and is fixed here.** `RunPanel.tsx` computed a three-way partition — live, this box, other boxes — and then rendered it only when `scope.box === null`, which is precisely when `mine` is empty by construction. So a screen with a box selected threw the grouping away and drew the server's order, and a screen with none drew the groups and could caption a section `other boxes` with no box to be other than. Both halves backwards at once, which is why neither looked wrong on its own.

**What would reopen this: a cart that is never used with more than one box.** The whole cost of this entry is the list shape on the wire and the per-box reading state; if every send is one box forever, the honest simplification is a single-box request again. The measurement is whether any `POST /pipeline/identify` carries more than one scope.

---

## D49 — The pricing answer is one file, and a card can be held back on purpose

**`decisions.json` decides the price and the run manifest only records what a join ran with, and a card may be withheld from a run on purpose.** Built from an interview the owner asked for on 2026-08-29. They had never been asked what they wanted a listing price to BE — `match` on `market` was the CLI default running by accident through every run this project has done. Their answer: show all the CSV data at the moment of the decision, because they intend to hand-price.

**On volume, which inverts every measurement taken before it**: almost everything coming next is above $0.40. Measured across the two Pokemon runs on disk — 596 cards, 153 SKUs — the total value of every per-item pricing decision available was **zero**: box 2's export tops out at $0.74 and stocks no Near Mint row at or above the threshold, and Gate B's `import-listed.csv` is header-only. The honest reading of that history is a screen whose job is to report there is nothing to do. The owner says the next boxes are the other thing, and the export bears out the mechanism: Near Mint **normal** is 9.5% listable, **reverse holo** 40.6%, **holo 76.2%**. The exception rate is a function of the finish claim made at capture, so it is predictable before a run starts and it is about to go up.

### Part one — the file decides, the manifest records

Two bugs in one seam, and the owner's instruction on being shown them was to resolve the conflict.

- **`emit` priced from the run MANIFEST and printed the rule from `decisions.json`.** An operator who set `"rule":"undercut:5"` got a run that printed `rule=undercut:5` and wrote every row at market. That file's module docstring has called it *the pricing decision, as a file rather than as a flag* since it was written, and `rule` was the one thing in it that decided nothing.
- **`join` assigned `choice.rule` and `choice.basis` back from the run** immediately after printing that it was merging into an existing `decisions.json` and keeping your edits. Measured: `markup:100` on `low` reverted to `match` on `market` on a plain re-join while `sub_threshold` beside it survived — so the file looked merged and was not. `join` is free, re-runnable and re-run routinely, so this was not an edge case.

**The file is the authority; the manifest keeps `rule`/`basis` as the RECORD of what a join ran with**, which `report.txt` prints. A record of what happened and the answer to what should happen are different facts and only one may be authoritative. `--rule` still seeds the file on the FIRST join, because a document that cannot answer its own question is not a document.

**Both commands now refuse `UnknownRule` and `UnknownBasis` with a sentence.** They are `ValueError` subclasses and NOT `MalformedDecisions`, nothing above `cli/__main__.py` caught them, and `PUT /pipeline/runs/<name>/decisions` writes this file with no validation at all — so a screen could put a run into a state where `emit` answered with a traceback. T7's `check_pricing_authority` block holds all of it, and both halves were **observed failing against the old code**.

### Part two — a card can be withheld, and the hold says why

The owner: bullish on a price going up and not wanting to list any right now, and wanting a way of flagging that the hold is intentional.

Before this there was no way to say it. `overrides` demanded a price, `"unlisted"` was accepted only under `no_market_data`, and a card with a market price had no representation for *not this run*.

**`overrides` gains two shapes and every existing shape stays byte-identical.** A scalar is a price. The bare string `"unlisted"` is a hold with no reason — the spelling a terminal user types, and the one `no_market_data` has accepted since D9. An object is a hold **with** a reason, which is what the screen writes:

    "9114773": {"withheld": "bullish", "watch_above": "12.00", "note": "waiting on rotation"}

**A strict widening, not a new failure mode**: before this a dict reached `_price`, `Decimal(str({...}))` raised, and it was already a clean `MalformedDecisions` rather than a traceback.

**`withheld` and NOT `held`, which is D26's rename for D26's reason.** `store/master.py:Listing.held` already means copies **TCGplayer** is holding — the opposite direction — and `_listing_hold` in the capture server means a box may not be deleted. D26 renamed `removed` to `retired` because a state sharing a word with an existing one makes both unreadable.

**The vocabulary is disjoint from the two it could be confused with, and no word appears twice.** `WITHHOLD_REASONS` is `bullish | keeping | next_batch`, against D26's `pulled | damaged | lost | given_away` (the CARD left inventory) and D37's `wasted_position | cannot_settle | not_listing` (the QUESTION was closed). `next_batch` rather than the obvious `not_yet`, because `not_listing` is already a stand-down reason and the two read as one word at the 10px a machine string is drawn at.

**A withhold is none of the three things it sits beside.** Not a retirement: the card does not move, does not change state, keeps its slot and its photograph, and is sellable the moment the hold is lifted. Not a stand-down: nothing is asking — the card resolved cleanly, with a catalog row and a market price, and what is refused is the *listing*. Not a sale: no count at `pushed`, `staged` or `live` moves. What is withheld is one run's import row.

**Holds are absent from `dispositions()`, and that is the survival guarantee rather than tidiness.** `emit` refuses the whole run when that mapping names a SKU the batch does not hold, and `prices_for` refuses again per game. A withheld SKU is precisely the one most likely to fall out of a later run — it was withheld *because* it is not being listed — so letting holds reach those checks would mean the act of holding a card back eventually breaks `emit` for the entire run, with no control anywhere able to clear it. For the same reason `prices_for`'s `withheld` set carries **no unknown-key check**, unlike the dispositions beside it.

**A header-only import file was one line away and is closed here.** `prices_for` leaving a SKU out and `import_rows` skipping its row is correct — but `emit` decides whether to write a file AT ALL from whether its SKU set is empty, and the writer emits the header before it iterates rows. A game whose every listable SKU was held would have written a header-only `import-listed.csv` and reported `listed 0 row(s)`. That is the Gate B shape exactly, and `_game_only` subtracts the holds instead.

**The price threshold is built, not deferred, and the argument that nearly deferred it was wrong in an instructive way.** A watch looked pointless on the grounds that it can only fire while somebody is already looking at the price. They are not: a re-join is driven from `#/runs` (D39), and `join` is free and re-runnable precisely so it can be pointed at a **refreshed export** — the only moment a market price has moved and therefore the only moment a watch has anything to say. `Decisions.watches(matches)` is a method rather than a `warnings` entry because `warnings` is a zero-argument property and cannot see a price.

**A hold lives in its run and dies with it.** `decisions.json` is per-run, so a hold survives every re-join of its own run — which is where it does its work, since a box is identified once and re-joined many times — and a **second** run over the same box starts with none. That is a real limit and the screen says so in words. A durable per-SKU home outside the run directory — beside `Listing` in the store, or a standing `holds.json` beside the queue files — is **recorded and deferred**: it is a schema change, a route and a client function, and scope is argued.

**A second cost, named because nothing else would say it.** `emit` writes a card's identity only for SKUs that reached a file, so a withheld SKU's copies keep `state: captured` and carry no `sku` — invisible to `GET /search` and every SKU-keyed surface until the hold is lifted and the run re-emitted.

### Part three — the screen, built 2026-08-30

`#/pricing` is the seventh route, and it is where the owner sets by hand what every SKU a run matched will list at. One row per SKU, sorted market descending, carrying every export column that holds data. It draws no photograph on the row, no price type-size bands and no solid accent fill; the box, the cart and the money gate stay on `#/runs`, and **nothing here spends**.

**After the review queue and not before it**, which is the owner's ruling and reverses what the first design pass proposed. Answering the queue changes what the next join resolves, so pricing before the queue is worked prices a set that is about to move.

**The suggestion writes nothing, and that is the load-bearing decision of the whole screen.** The run's rule prefills every row as a visible suggestion; the first digit typed clears it, Enter commits and advances, and `m`/`d`/`l`/`s` snap the price to a named export column. But an untouched row writes no key at all — because an override is layer 1 of the ladder and beats the rule at layer 4, so a screen that wrote its hundred suggestions would produce a run where **changing the preset silently changed nothing**. That failure has no symptom. `pipeline/decisions.py` states the rule it rests on in one line: nothing here is ever defaulted on your behalf, and that is the entire point. If a later session finds itself wanting a *write all suggestions* button, that button is this defect.

**The keyboard works with the hands in a field, which no other screen here does.** Every other handler in the app returns on `isEditableTarget`; on this one the hands are in a price field essentially always, so that rule would make every letter dead. What makes it safe is that the field's alphabet is CLOSED — `[0-9.]`, one dot, two decimals, enforced at `beforeinput` — so a letter is unambiguously a command and there is nothing to disambiguate. That closure is the entire safety argument and may not be widened without taking the keyboard with it.

**A preset prices what it can and names what it could not**, which is the owner's ruling over refusing the whole press. Measured: 394 of 2,476 listable rows in the wide export carry no `TCG Low Price`, so a Low-based preset genuinely cannot price every row, and `SkuMatch.list_price` is `None` there — which `tcgcsv.set_writable` would turn into an import row carrying a quantity and no price. The three presets and their numbers are the owner's: match market, `Market −5%`, TCG Low −1%.

**The run comes from a picker or from the URL, and never from storage.** D39's handoff exists because `#/inventory`'s mass-select is the only one in the product and a second would be two answers to *which cards*. A run name has no such property — `GET /pipeline/runs` reads the runs directory and is the single source — so a picker here cannot disagree with anything, and `#/runs` links a specific run as `#/pricing?run=<name>`. A link, not a handoff: no second `sessionStorage` key and no clearing rules. **The hash router did not strip a query until this landed**, so the link matched no route and rendered `NoSuchView` — a defect invisible from either the route table or the screen, and fixed in `currentPath`.

**The photograph is on demand, toggled by one key, and names which copy it is drawing.** The owner asked the question that settles it: how it resolves when multiple captures of the same card exist. A SKU averages five copies with five photographs, they are the same card by construction, and **there is no quality signal worth trusting** — confidence is the tempting one and is exactly wrong here, since T1's recorded misses are confident answers with the digits wrong. So the pick is the first in box-walk order, captioned with its real position and `1 of N`, and steppable. The stepping is what makes an arbitrary pick safe, and it earns a second job: five photographs answer *are these actually the same card*, and if they are not, the identification was wrong.

**`scripts/docs-audit.py` gains a `withhold reasons` row**, reconciling `WITHHOLD_REASONS` across `pipeline/decisions.py` and `app/src/holds.ts`. Blocking, because a mismatch is provably wrong — and it matters more here than for the review vocabulary, since `PUT .../decisions` validates nothing and the screen's only defense against writing an unparseable file is that the two declarations agree. Mutation-tested in both directions.

**The save loop was wedged from the day it shipped, and every case in its own spec was green throughout** (found by the owner 2026-08-30: price changes stuck on perpetually saving). The effect that writes `decisions.json` read the `saving` STATE it raised itself, so `saving` was in its dependency list — raising it re-ran the effect, and the re-run's CLEANUP set the in-flight closure's `live` to false. The response landed on a dead closure, so neither the clear nor `setSaving(false)` ever fired. **On the first save of every session**: the indicator read `saving…` forever and the guard `if (… || saving) return` then refused every later write. The operator could price a box, watch each answer draw, and have one row reach the file.

**It passed fifteen cases because the PUT really does go out.** `app/tests/pricing.spec.ts` asserted what the screen SENDS — the load-bearing absences this entry rests on, and one body with one answer in it — and never that a write COMPLETED. What that suite could not see is everything after the request: the indicator returning to `saved`, and a second answer being sent at all. Both are asserted now, and both were observed red against the old code with the other fifteen still green.

**`dirty` is a comparison now, not a flag, and that is the half that is not cosmetic.** The effect's own comment promised that a change during one write re-runs when it lands, and a flag cannot keep that promise: it cannot tell *the write I just sent* from *the write that landed while it was in flight*, so clearing it on a response discarded whatever had been typed since that response left — silently, with the indicator reading `saved`. The screen holds the document the server last confirmed and `dirty` is object identity against it, so a write clears only what it carried and anything typed during a flight is still unequal when it lands. The guard is a ref, which is what lets `saving` stay in the dependency list doing the one job it is good for — re-firing the effect when a flight ends, since everything a completion changes is a ref and a re-render is the only thing that can ask whether more is owed.

**A refused write is not retried in a spin.** `dirty` correctly stays true after a failure — the server does not have those answers — so without a record of the document that failed, the loop would re-fire the instant `saving` went false, forever. The next keystroke makes a new document and the retry happens then.

**The preset wrote a key nothing reads, so picking one changed the screen and not the run** — the owner's own analysis, 2026-08-30, and it is exactly right. `applyPreset` wrote `preset: <key>` into the document. `pipeline/decisions.py:parse` does not know that field and `to_payload` does not emit it, so the next join dropped it, and `rule` and `basis` sat at `match`/`market` throughout. Pressing `Market −5%` re-rendered every suggestion on screen and moved nothing `emit` reads.

**The comment directly above that line said `A PRESET WRITES rule/basis AND NO OVERRIDE`.** It described the design; the line under it did something else, and nothing compared them. Measured on the owner's riftbound run, on disk: `preset: market_undercut_5` sitting beside `rule: match`, `basis: market`, with **2 overrides across 50 SKUs** — so 48 cards were about to list at a price nobody had chosen, and the screen had shown all of them at −5%.

**It is this entry's own named failure reached by the other road**, which is why the fix is the rule and not the suggestions. The paragraph above refuses to write the hundred suggestions into `overrides`, correctly, because an override beats the rule. That refusal is only half an answer: if the suggestions must not move, then **the rule at layer 4 has to**, and it never did. A preset now writes `rule` and `basis`, which is what that comment always claimed.

**The active chip is derived from `rule`/`basis` and is never stored.** Nothing on this screen said which rule was live, and that is most of why the dead write survived — pressing a chip appeared to work, because the suggestions really did change. A REMEMBERED selection would have been a second answer to *what will an untouched row list at*, and the pair the pipeline reads is the only one that can answer it; so a rule typed by hand into `decisions.json` on `#/runs` correctly lights no chip rather than lighting a stale one.

**`scripts/docs-audit.py` gains a `pricing presets` row**, reconciling `cli/cmd_join.py:PRESETS` against `app/src/Pricing.tsx:PRESETS` on all three fields — key, rule and basis. Blocking, for the reason the `withhold reasons` row gives verbatim. It reads the Python side by `ast` and resolves `pricing.RULE_MATCH` out of `pipeline/pricing.py` rather than importing anything, because naming the constant is right and flattening it to a literal to please a checker is the inversion D16 forbids. Mutation-tested in both directions.

**What is still not built, and the owner found it in the same pass**: `server/pipeline_routes.py` computes `remembered_sub_threshold` and ships it on the pricing route, `app/src/types.ts` declares it, and **no component reads it**. The sub-threshold disposition is still typed into `decisions.json` by hand on `#/runs`. It is `CLAUDE.md`'s route-is-not-a-feature rule in its mildest form — a server half with no client half — and it is named here rather than built because a control that answers D9's per-run disposition is a design question, not a wiring one.

**What is not built, named rather than left to be discovered**: no durable home for a hold outside the run directory; no cross-run view of what is being held; no search or sort control, because the sort is the hierarchy and a re-sort under a finger is D28's defect; and no `Custom` preset — any other rule or basis is typed into `decisions.json` on `#/runs`, in the text editor D33 chose, and a re-join regenerates the suggestions.

**What would reopen this: a hold nobody lifts.** If holds accumulate across runs and are re-set by hand every time, the per-run home is the wrong one and the deferred durable store becomes the answer. The measurement is whether the same SKU is withheld in two runs over one box.
## D50 — An interactive element's feedback is the product's, not each stylesheet's

**Cursor and hover feedback are answered once in `base.css` for every control kind, not left to each screen to remember.** Built 2026-08-29 on the owner's report that the mouse cursor did not change correctly for what it was over. They then granted hover darkening, permission to edit the fixed palette, and permission to build a guard retaining standardization across interactive elements.

**The palette has been locked since 2026-08-12 and this is the first token added against the lock.** `docs/DESIGN.md` records that every value was chosen by the owner from rendered alternatives rather than described in prose, and that a token nobody can argue with is a token the next session quietly replaces. `--field-hover` was not chosen that way — it was measured, and the owner granted it against the lock. Recorded here so a later session reads it as a grant with a reason rather than as drift, and so the interview's authority over the other values is not weakened by one addition beside them.

**The defect was never mostly about color, and the measured premise had to be corrected in public first.** The opening count was that 39 interactive elements had no `cursor` rule any selector could reach, which is true of the CSS and wrong about the effect: most of those are `<a href>` and `<input type="text">`, which the user agent already answers correctly. **The real concentration was the DISABLED state, which no per-file rule was looking at.** Of 65 distinct control shapes the app can draw, 41 had a wrong cursor: 30 clickables went on saying `pointer` while refusing the click, 7 text fields read `text` while refusing a character, 2 `<select>`s read `default`, and 2 buttons read `default` disabled where 18 siblings read `not-allowed`. Missing `:focus-visible` was **zero** — `base.css` already had a global ring, so keyboard parity was never the gap, which is the one thing everybody would have guessed.

**A default in the reset, not a note asking each screen to remember.** The six stylesheets that declared no cursor at all are not badly written; they are the ones whose author had no reason to think about it. `base.css` now answers for `button`, `select`, the three toggle input kinds, `[role='button']`, a label that owns a toggle, and the disabled arm. It is the same argument the focus ring one block above already makes, and the same one `app/eslint.config.js` makes for a bug that earned a rule: **a paragraph in one file guards one file.**

**The floor's guarantee is cascade order, not specificity, and the first draft got that wrong in its own comment.** It claimed every rule was one specificity (0,0,1) so any class outranks it. That is false for eight of the eleven selectors — `input[type='checkbox']` is (0,1,1), `[role='button']` is (0,1,0), and the whole disabled arm is (0,1,1). The behavior was correct anyway, for a reason the comment had not stated: `main.tsx` imports `base.css` before every component sheet, so a tie goes to the component. **Corrected rather than left standing**, which is D41's own recorded failure — a comment whose premise had been deleted while its conclusion stayed — caught this time inside the session that wrote it. The property to preserve is the import order; moving `base.css` below a component stylesheet silently inverts the floor.

**The disabled arm outranks a rest-state class on purpose**, which is the one place the floor is deliberately not a floor: `button:disabled` at (0,1,1) beats a bare `.foo { cursor: pointer }` at (0,1,0), so off beats on. A screen wanting a different disabled cursor still wins with a class of its own.

**The token: `--field-hover`, #6B6E73, and the free reuse was refused on a number nobody would have computed.** `--field` at 3.36:1 is the quietest edge WCAG 1.4.11 permits, so a text field had no hover response at all. The obvious answer is `--muted`, an existing value needing no grant — and it fails, because **the criterion here is contrast against `--ink`, not against the ground.** Every focus treatment on these controls is an ink `outline`, so the question a hover border must answer is whether it can be told apart from focus:

    --field   #8C8C8C   5.93:1 vs ink   rest, and no hover response at all
    this      #6B6E73   3.89:1 vs ink   1.52x the rest edge, still clearly not focus
    --muted   #4E5157   2.50:1 vs ink   2.37x the rest edge, and READS AS FOCUS

On surface / bg / hover it is 5.12 / 4.99 / 4.69:1, clearing 1.4.11's 3:1 on all three grounds a field is drawn on. **It composes with focus rather than competing**: hover darkens the border, focus draws an outline outside it at a positive offset — two properties in two places, so a control that is both says both.

**Named for one state of one job, per the rule `--field` sets for itself.** `--field-hover` cannot grow into a button border the way `--edge` or `--control` would have within a session. It reaches the seven typed-into controls and nothing else. **It does not license a hover color for buttons** — those already lift to `--hover` — and it adds no second hover ground, so `docs/DESIGN.md`'s rule that every text token clears 7:1 on every ground is untouched: this token carries no text and is never painted as a background.

**One rest-state change came with it and is the owner's to overrule.** `CaptureScreen.css`'s `.capture-entrybox` bordered with `--line` (1.24:1) while every other typed-into box in the product used `--field` — so the token created for exactly this control had missed one, and the box could not take a hover state that started from a different edge. It is `--field` now, which is `docs/DESIGN.md`'s existing rule applied rather than a new one. The cost is visible and is on the screen the owner spends the most hours in: that border gets darker at rest. Named here rather than buried, because it is the one change in this entry a person will SEE without hovering anything.

**The guard is a spec, and without it this entry would have been written for nothing.** Nothing in `app/tests/` asserted a cursor anywhere: `make design-check` was green through the whole defect and would have stayed green through a total regression of the fix. That is the failure mode `base.css`'s own focus-ring comment warns about, and it is why the owner's second grant matters more than the first. `app/tests/cursor.spec.ts` asserts the CLASSES — a clickable reads `pointer`, a disabled control reads `not-allowed`, a text field reads `text` — across every route, rather than pinning a selector list that would go stale the day a screen adds a button.

**It asserts the rule, never the roster**, which is the same distinction D40 draws for the copies row: pinning today's numbers goes green on any later change that moves the defect somewhere else. A new button that forgets its cursor has to fail this spec, and it only can if the spec discovers controls rather than being handed them.

**And it did not, for two days, one level up — the ROUTES it swept were a pinned roster.** `app/tests/cursor.spec.ts` shipped on 2026-08-30 asserting the rule about controls off a hand-typed list of seven hashes. D69 added `#/orders` and `#/shipping` that same day and D70 added `#/codes`; none reached the list, three screens were swept by nothing, and `make design-check` was green throughout — a roster missing a route does not fail, it walks the routes it has. Repaired 2026-08-31: the spec reads the nav strip, which `App.tsx` renders from the same table it routes from, so a route registered next month is swept with no edit to the spec. `#/codes`'s disabled buttons were reading `default` and are the 30-of-41 class this entry was written for, found the moment the roster widened. **The lesson this entry did not carry is that "never the roster" has to hold for the ROUTES too**, and for the specs where a pinned list is deliberate — `app/tests/nav.spec.ts`'s Cmd-arrow ring (D51) is one — `scripts/docs-audit.py`'s `route rosters` row now reconciles the list against `App.tsx`'s table at the commit.

**What is deliberately not done.** No `:active` pass — it is neither hover nor cursor, only three files have one today, and adding it to ~20 controls is churn with reflow risk. No hover state anywhere may change `border-width`, `padding`, `font-size` or `font-weight`: **D28's defect was the review queue's list moving under a finger already travelling toward a target**, and a hover that reflows is that defect in miniature on every screen. Measured at zero reflow offenders across all seven routes — and RE-MEASURED on 2026-08-31, when the product had ten, as zero offenders across all 64 `:hover` rules in all 26 sheets under `app/src/`. The second number supersedes the first and is the stronger claim: the original walked the routes a browser drew against an empty store, so a rule on a control that did not render was outside it, and the re-measurement reads every rule whether or not anything draws it today.

**What would reopen this: a screen that wants a control to say something else.** The floor is overridden by a class, deliberately, so a genuine exception costs one rule and one comment saying why. What must not happen is a screen going back to saying nothing at all — that is what the guard is for, and a spec that starts skipping routes has repealed this entry without anyone arguing with it.

---


---

## D51 — Cmd-arrow steps the strip in the order it is drawn, and it is the one modifier the shell takes

**Cmd-left and Cmd-right step to the previous and next route in the order the nav draws them, and the ring never wraps.** Built 2026-08-30, from the owner pressing a key that was already answering them wrongly: Cmd-arrow was not moving in order between capture, runs, review, pricing and inventory.

**The shell had a jump and no step.** `app/src/App.tsx`'s `,` chord names a destination — `,c`, `,r`, `,q`, `,p`, `,i` — and has never had a way to say *the next one along*. That sentence is worth having because the nav is not an arbitrary set of links: D31 and D39 order it as the work happens, shoot then run then answer then price then look up, and `group` was added so the row says that out loud. An ordered row whose only key is a jump is a row whose order the keyboard cannot use.

**What was answering the press instead was the browser's history, which is a different question wearing the same shape.** A back stack orders by when a screen was ARRIVED AT, so Cmd-arrow walked whichever two routes the last two presses happened to be, in whatever order they were visited, and at the bottom of the stack it left the app entirely. It is not that the browser was wrong; it is that it was answering *where was I* while the hand was asking *what is next*.

**This is the one place the shell takes a modifier, and `LEADER`'s rule is narrowed rather than broken.** That comment read that modifiers are NEVER part of it, and gave the reason — Cmd-comma belongs to the browser and the OS, and a shell that eats it has broken something it does not own. It is amended in place to say `NEVER PART OF THE CHORD`, which is where the argument actually lives: a chord is two unmodified presses, and a leader needing a modifier would be competing for exactly the key space it was invented to escape. The step is not a chord.

**It costs a browser shortcut and that is paid rather than argued away.** Cmd-arrow is Back and Forward in Chrome and in Safari. What makes it affordable is that neither browser has only one way back — Cmd-[ and Cmd-] and the two-finger swipe are all untouched — and that the key is handed to the page at all, which not every Cmd shortcut is: the reserved set that never reaches a listener is Cmd-N, Cmd-W, Cmd-T, Cmd-Q and their kind. **The half no test in this repo can see is whether the browser then honors `preventDefault`**, because Playwright presses keys through the debugging protocol, which never fires a browser shortcut in the first place. `app/tests/nav.spec.ts` says so in its own header, and this is the paragraph to reopen if a press ever both steps and goes Back — the remedy then is a different pair of keys, not a different handler.

**The ring is the routes that have a key, in the order the nav draws them.** Both halves are derived rather than listed a second time:

- **Which** — `hotkey !== undefined` already means *reachable from the keyboard*, and the two rows without one are without one for reasons that apply here word for word. Fulfillment must not be arrivable by accident, because it renders no way out; the gallery is not a step in any loop. A second list is a second answer to a question `ROUTES` has already answered, and the first screen added to one and not the other is the defect.
- **Order** — `GROUP_ORDER` first, then the table, which is what the nav actually renders rather than what the table alone says. They agree today. The day somebody re-orders `ROUTES` without touching `GROUP_ORDER`, a ring built from the table alone would step in an order the strip does not draw — and stepping in the drawn order is the whole of what this is for.

**Never a wrap, and every end stops.** `BoxBrowse` says it in those words about its own arrows and the reason transfers: a row that starts again is a row you can no longer count along. **The press is consumed at the ends all the same**, which is that file's second rule and the half that makes them readable — a refusal is still this handler answering for the key, and letting it fall through would mean Cmd-left sometimes steps a route and sometimes leaves the app for whatever the history stack holds. That is the *not in order* this entry exists to fix, arriving by another road.

**A screen outside the ring keeps the browser's key.** The gallery is the live case: it has chrome, so the listener is mounted, and it is deliberately not a step in the loop — so there is no next one along, and the honest answer is to leave the press alone rather than invent a landing.

**Three refusals, each answering a key that is somebody else's.** A bare arrow is the screens' — `BoxBrowse` walks a box with them and `RunPanel` steps the crop preview — so the modifier is not decoration, it is what keeps the shell out of their key. Alt is excluded outright rather than merely not required, because Cmd-Alt-arrow is *previous/next tab* in Chrome and a step that also changed tab would be answering for a press it did not read. And in a text field Cmd-arrow is the caret going to the start or the end of the line, which is what the hands are doing when they are in one.

**It bubbles, where the leader captures.** The leader takes the capture phase because its whole purpose is to consume a key another screen has bound, and that bluntness is bounded by having to be armed one press earlier. A step key is never armed, so a permanent capture-phase listener would be a standing claim on a key it mostly does not want — and it needs none, because every arrow handler in the app returns on a held Cmd before it reads the key. What it does need is `preventDefault`, which works from either phase.

**Arriving anywhere disarms the leader, and that is a hole this entry found rather than made.** A chord is spent on arriving, so an arm that survives an arrival is an arm nobody is holding — and `useLeader`'s own comments already say what that costs: the next keystroke is eaten on a screen the operator did not press it from, which on the capture screen is a card that went past the lens unrecorded. It was already reachable by the browser's Back and by a nav link; the step would have been a third way in. One effect on the path closes all three.

**The strip advertises it once, at the end of the ring.** `docs/DESIGN.md`'s *every choice shows its key* — a binding nothing advertises is a binding only the person who asked for it will ever press. One hint rather than one per link, because there is one binding and it reaches whichever screen is next, where `,C` is per route because the destination is what changes. It trails the last route the step can reach rather than the end of the bar, where `.app-nav-group-aside`'s auto margin would have stood it beside the two routes it cannot. Drawn in the same 10px chip as every other key in this app but **deliberately not wearing `.app-nav-key`**, because that class lights up when the leader is armed and the step is never armed — a chip claiming a state it does not have is worse than no chip. `aria-keyshortcuts` on the nav carries the same fact for a screen reader, which two arrow glyphs could not.

**The first test this shell has ever had is `app/tests/nav.spec.ts`.** Neither keyboard had an assertion of any kind: `make design-check` covered six screens and nothing covered the chrome all six sit under. Seven cases, and the strongest are the two ends and the three refusals. Four mutations were observed failing before they were kept — a wrapping ring, a dropped editable-target guard, a dropped modifier guard, and the leader disarm removed.

**Two cases were written, found to be incapable of failing, and changed — which is the part worth reading.** The disarm case asserted `not.toHaveAttribute('data-armed')`, and that assertion retries: `CHORD_MS` expires on its own after a second, so it went green against a build with the disarm deleted. It now reads the attribute two frames after the hash changes, ~30ms into a 1000ms window. And a case pressing the step on the Fulfiller's view was deleted outright: it is refused by `enabled` AND by the ring, so no single mutation makes it fail. What guards him instead is the end-of-ring assertion, which goes red the moment a `hotkey` is added to his row — the mistake that would actually put him in the ring.

**What would reopen this: a browser that keeps the key.** If Cmd-arrow turns out to both step and navigate, the fix is a pair the browser does not claim — and the obvious candidates, Cmd-[ and Cmd-], are the same shortcut by another name. `,` plus an arrow is the one that costs nothing, since the leader already consumes whatever follows it.

---

---

## D52 — The photo URL names a photograph, because a slot's occupant changes under it

**The card band's photo URL carries `?card=<capture_id>`, so it names a photograph rather than a slot.** Built 2026-08-29, from the owner reporting that deleting a card felt risky because the delete did not kick in quickly, making you think you needed to delete more when in fact it eventually showed that it really was deleted.

**Nothing was slow, and that is the finding.** Measured against a hardlinked copy of the owner's real store, box 2, 543 cards: `POST /inventory/2/180/remove` answered in **288 ms** having shifted 363 cards, the three reads behind it returned in **116 ms**, and the walk, the count, the facts and the receipt were all correct **500 ms** after the press. The `inventory.json` write is **0.29 s** at its worst — deleting card 1 of 543 — and `GET /inventory` over the whole 715-card store is **37 ms**.

**What the operator is actually looking at is a photograph of the card they just deleted.** `app/src/server.ts:photoUrl` answers `/photo/<box>/<index>`, which is an address for a SLOT rather than for a card, and D10 ruling 1 slides a different card into that slot. The card band kept drawing the deleted card's picture over its replacement's facts, at the same position label — so the one large, unambiguous thing on the screen said nothing had happened while four small ones said it had. **The reading that makes this dangerous rather than untidy is the owner's own**: the next press deletes the card that slid in, which is a real capture with a real photograph, and it is not refused, because the aim check is satisfied by the record the screen just re-read.

**Three operations change a slot's occupant and only one of them was ever guarded.** The mid-box delete (D10 ruling 1), the undo that releases an index for the next capture (D10), and D26's re-shoot. Only the third had an answer, and it was a nonce appended by the one screen that knew it had just replaced the bytes.

**Three repairs, in the order they were built, and the first two are kept despite not being sufficient.** Recorded as a sequence because each one looks like the whole answer until it is measured, and a later session will reach for them in the same order.

1. **A validator on the server, which is the repair this repo had already specified in writing and never built.** `photoUrl`'s comment said the server sends no validators and the fix is a cache header on the server, and it was right about the diagnosis for four months. `GET /photo` now sends a strong `ETag` — sha256 of the bytes, truncated to 128 bits — and `Cache-Control: no-cache`, and `_photo` answers `If-None-Match` with a 304. **Necessary and not sufficient**: a header is a rule about reusing a cached RESPONSE, and an `<img>` React keeps in the document never asks for one.
2. **The occupant in the element's React key, so it remounts.** It does remount — measured, `sameDomNode: false` across a delete — and **the picture still did not change**. Chrome satisfies a second load of an IDENTICAL URL within one document from its in-memory resource cache, which consults neither the ETag nor `no-cache`: one resource-timing entry, `transferSize: 0`, before and after. Kept, because a remount is what makes step 3 issue a load at all.
3. **The capture id in the URL.** `?card=<capture_id>` on the card band's photograph. The two loads are now different requests, so there is nothing for the memory cache to reuse, and the correct photograph is on screen ~**1 s** after the press. Verified end to end in a browser against the copied store, with the walk, the facts, the count and the picture all naming the same card.

**The stamp is not the cache-buster `photoUrl` refused, and the distinction is the whole license for it.** That comment rejected a cache-busting query parameter minted there, and it was right: a NONCE is a value that never repeats, so it defeats caching by construction and papers over the missing header. `capture_id` is stable for the life of a photograph. It makes this URL name the photograph rather than the slot, so a card keeps one URL forever and the route caches **better** than it did — and a URL changes only when the thing behind it does. The re-shoot exception that comment already carries is now the same rule arriving one re-read early rather than a second mechanism: `nonce` IS the new capture id.

**It is one screen, and the reason is specific rather than a judgement about effort.** Every other site that draws a stored photo keys its element on a POSITION that moves with the card — the review queue's entries are re-keyed by the renumber itself, the Fulfiller's card and the two confirm panels are opened for one copy at a time. `BoxBrowse`'s card band is the only place in the product that holds a slot SELECTED while its occupant changes underneath, which is exactly what a delete does to it.

**What is not fixed, named so a green suite is not misread.** The in-document memory cache is still reachable anywhere two different cards are drawn from one slot URL in one document — the review screen's photograph after a renumber is the realistic one. The ETag makes every genuinely new load correct, so the residual is narrow, and the remedy if it ever bites is step 3 at that site rather than a new mechanism. And a record written before capture ids existed carries `null` and falls back to the bare slot URL: `do_remove_card` aims by the same field and is blind in the same place, so a Reload is the answer in both.

**`SearchCopy` is deliberately not widened to carry one.** `app/src/types.ts` argues that a search result which also carried `confidence` and `capture_id` would invite a second inventory view to grow inside a search result, and none of the sites fed by it needed the stamp. Left alone rather than widened for symmetry.

**Covered by `harness/tests/t7_store_and_seams.py:check_photo_cache` over real sockets** — the headers, the 304, the weak comparison, `If-None-Match: *`, and the case that is the defect: the same URL with the same tag answers 200 after a shift, under a new tag, with the neighbor's bytes. And by `app/tests/inventory.spec.ts`, which asserts the URL carries the occupant before and after a delete. **Both were mutation-tested**: a slot-derived ETag takes the T7 case red, a dropped `Cache-Control` takes another, and reverting the stamp takes the browser case red.

**What would reopen this: a photograph that is slow rather than wrong.** Every measurement above says the data path is fast, so nothing here buys latency. If the walk ever feels slow after this, the thing to look at is the 304 round trip per card — and the honest fix then is a long `max-age` on a URL that already names its photograph, which this entry makes safe and deliberately did not take.

## D53 — One link, always live, and the restart discipline becomes machinery

**`make up` runs both servers under a supervisor that reloads them when their source changes.** Built 2026-08-30, from the owner asking to stop running the project the way it had always been run: go to a link, get the live version against local storage, and have an edit picked up without remembering to restart.

**The restart shenanigan is a recorded defect, not an inconvenience.** `docs/GATES.md` holds the measurement: `store/master.py:now()` was changed to milliseconds at 20:16, box 95's run at 22:08 still wrote whole-second stamps, and the cause was not the code — the server process serving it had started before 20:16 and was holding the old code in memory, which no commit can reach. That file calls it a restart discipline. A discipline is what you have instead of a guard, and this repo has been here before: D42 exists because it already was a line nobody had written, and main moved under three live worktrees twice in one day. `scripts/serve.py` is that lesson applied to the server.

**`make server` and `make dev` are untouched.** A session wanting a foreground server in a terminal it is watching still has one, and that one still does not watch files, so `docs/GATES.md`'s discipline goes on governing it.

**Rejected, and it led until the owner answered: building the app to `dist` and serving it from the capture server.** It collapses two processes into one, and `app/package.json` has carried an unused `build` script the whole time. It is the wrong answer to *this* request, because a built bundle has to be rebuilt — it would ADD a step to remember in exchange for removing one. Vite stays, and it was already the half that worked.

### The drain is counted on requests, never on threads

Both halves measured on this machine's Python, and the obvious implementation is a no-op that looks like it works:

- `ThreadingHTTPServer` sets `daemon_threads = True`, and `socketserver._Threads.append` **discards a daemon thread** rather than recording it — so `_threads` is always empty and the join inside `server_close()` already does nothing. A version trusting it would pass every smoke test and lose requests.
- Setting `daemon_threads = False` does not fix it either. `protocol_version` is HTTP/1.1, so a handler thread lives for the whole keep-alive CONNECTION rather than one request, and `BaseHTTPRequestHandler.timeout` is None — the join would block forever on an idle tab.

So a counter wraps `_dispatch`, which every verb funnels through and which is entered after the request line is parsed and before the body is read. **`server_close()` first, then drain** — in the other order the wait races arrivals it cannot refuse and never reaches zero.

**Why it is worth building: `store/session.py:Store.write()` replaces four JSON files in sequence.** Each is atomic alone and none is atomic as a set, so a kill between them leaves a torn store. That risk exists today at Ctrl-C frequency and auto-restart multiplies it, which is why the drain is a PREREQUISITE for the watcher rather than a refinement, and why the two were built and verified in that order.

**`DRAIN_SECONDS` is derived from the lock timeout and was never chosen.** `files.LOCK_TIMEOUT_SECONDS` is 30, and a capture posted while `./pkmnscan identify` holds the store lock legitimately waits that long before answering `store_busy`. A shorter drain would cut a request that was behaving correctly and about to say so — the same argument `app/src/server.ts` makes one process over for having no client timeout below 30s. T7 asserts the arithmetic rather than the number.

**An unhandled SIGTERM was strictly worse than Ctrl-C**, which is what made the handler necessary rather than tidy: with no handler the default disposition terminates the process with no `server_close()` at all. **The hard kill survives and is loud** — after the grace period the supervisor sends SIGKILL, because an unkillable wedged server is worse than a cut request, and it names `history.jsonl` as where to look.

### The watcher

**It refuses to restart into code that does not parse.** Auto-restart *guarantees* the watcher observes half-written code: an editor saves mid-keystroke and a formatter writes again a beat later. Changed files are `compile()`d first, and on failure the last code that parsed keeps running while the log names the file and line.

**Its limit is stated where it is implemented: PARSE errors only.** An `ImportError`, a module-scope `NameError` or a bad constant still kills the new child with no rollback. The containment is the fast-failure cap — after five quick deaths the supervisor **stops respawning and keeps running, still watching**, so a broken commit cannot make it spin and cannot make it die, which under launchd would flap it forever. The next save retries.

The fingerprint is a `{path: (mtime, size)}` dict rather than a digest so the log can NAME the file that caused the restart — the only thing connecting an unasked restart to the save that produced it.

**Mtime polling rather than `watchdog`, for two reasons.** The Makefile's invariant is that the capture server must never NEED `make venv`. And FSEvents coalesces and delivers directory-level events with its own latency, so the debounce would still be needed and the dependency buys nothing.

### The LAN half was never the server

**`HOST = "0.0.0.0"` has been there since it was written**, so the capture server has been reachable from the network the whole time and this adds no new listener. **The client was the broken half**: `app/devPort.ts` composes `http://localhost:${CAPTURE_PORT}` and `vite.config.ts` bakes it into the bundle, and on a phone `localhost` IS THE PHONE.

**So only the PORT is baked and the host is resolved at runtime** from `window.location`. It keeps every property the injected URL had — the port still comes from the same slot as the Vite port, so a worktree's UI still cannot be answered by another tree's server (D43) — and adds the one it lacked: it follows the address bar. This **honors `VITE_CAPTURE_SERVER`** rather than overriding it; that knob exists so the Fulfiller's device can be pointed at this Mac by address, which was necessary only because the default could not follow the address bar. It still wins, and is still the answer for a DIFFERENT machine.

**`server.host` was half the Vite change and the hostname test found the other half.** `host: true` makes Vite LISTEN on every interface; it does not make it ACCEPT every name. Vite refuses a request whose `Host` header it does not recognize — DNS-rebinding protection — so the app answered fine at `http://192.168.1.125:5366` and returned *"Blocked request. This host (\"pkmnscan.lan\") is not allowed"* at the name the operator would actually type. **Reaching it by IP is not a test of reaching it by name**, and only the second is the feature.

`allowedHosts` is `['.lan', '.local']` rather than `true`. A leading dot admits a domain and its subdomains, so the router's local record and Bonjour both work while an arbitrary public hostname pointed at this machine is still refused; both suffixes are non-routable on the public internet, which makes the narrowing meaningful rather than decorative. `true` would switch the protection off for every name and was declined.

**The origin allowlist needed no code change.** `PKMNSCAN_ALLOWED_ORIGINS` already existed, is documented, is read fresh per request, and **extends the defaults rather than replacing them** — and `*` is compared as an exact string, so it refuses everything rather than reopening the hole (T7 asserts this). The supervisor composes the value from this Mac's Bonjour name and `PKMNSCAN_LAN_NAME`. `scripts/serve.py` may not import the capture server, so it lifts `ORIGINS_ENV` with `ast` — the docs audit's own idiom; the alternative was a second hand-written spelling whose only symptom when it drifted would be writes silently 403ing from the LAN.

**What is genuinely widened: writes from a LAN origin are now accepted.** Reads always were. This is the point — D5 puts the Fulfiller on his own device — and it is still a real change to what a machine on the same network can do. Verified both ways: a write from the named host answers 201, one from an unknown origin still answers 403.

**`PKMNSCAN_LAN_NAME` lives in `.env`, not a shell profile**, and D47's amendment is why: an export in `~/.zshenv` fixes an interactive shell and does nothing for a process launchd starts, which reads no profile at all. **The owner's DNS is theirs and this repo does not touch it** — a DHCP reservation and a local DNS record on their UniFi map `pkmnscan.lan` to this Mac, and nothing in the code knows what the name is, which is the property runtime host resolution buys.

### The launch agent

**Generated, written outside the repo, and refused in a worktree.** A plist names an absolute path on one Mac; a tracked one would be D47's failure verbatim. `~/Library` is strictly better than gitignoring it — there is then no file in the tree to commit by accident — and `plistlib.dump` rather than a here-doc for `make launch-config`'s recorded reason: a hand-built plist is one escaping mistake from a file that presents as *the app does not start* rather than as a syntax error. `server/ports.py:agent_label` derives the label from the same slot as the ports, so two checkouts cannot install one label and silently replace each other.

**Main tree only, and the refusal is the design.** A worktree is deleted routinely and its plist would outlive it, leaving launchd retrying a path that is gone. `up`, `down`, `restart` and `status` work in every tree; only login-persistence is refused.

**`KeepAlive: {SuccessfulExit: false}` and not `true`, which is what lets `make down` win.** A process terminated by a signal is an *unsuccessful* exit to launchd, so `true` would restart the very thing `make down` had just stopped. The SIGTERM handler therefore always exits 0, and `make down` says — before the operator finds out tomorrow morning — that the agent will start it again at the next login.

**It also said `make down` prefers `launchctl bootout` when a plist exists, and that clause is deleted rather than repaired.** Both halves of its reasoning were wrong.

- **Wrong about the premise.** With the handler exiting 0, a signalled supervisor is a SUCCESSFUL exit and launchd leaves it alone, so signalling never needed avoiding. Measured: SIGTERM to a launchd-started supervisor left no process, no pid in `launchctl print`, and no listener on either port.
- **Wrong about which process.** `bootout` acts on the SERVICE, not on whatever is running — so when the live supervisor had been started by `make up`, bootout applied to nothing and `down` printed `stopped.` over a supervisor that was still up. `make launch-agent` then bootstrapped a second one, whose capture child could not bind, gave up after five retries, and overwrote `supervisor.pid` with its own pid. Two supervisors: one serving, one supervising nothing, and the pidfile naming the wrong one.

**It is the same defect as the liveness probe, one commit later.** Both are an action reporting success on the strength of something that did not apply to the process in question — the probe asked the socket instead of the child, this asked launchd about a service instead of the pid that was there. The probe was fixed and this survived, because it sat in a branch nobody re-read while fixing its twin. One path now, acting on the pid that is actually running.

**`EnvironmentVariables.PATH` is baked** because launchd gives an agent a minimal PATH and `npm` is otherwise not found, so the app half never starts while the capture server looks fine. If npm comes from nvm, an `nvm install` moves it and the agent needs regenerating.

### Liveness

**`make status` reports it, which it never has.** `ports_and_store()` printed which ports this tree WOULD use and never knew who holds them. **The third branch is what earns it: a port that answers while no pidfile in THIS checkout claims it** — D43's fault made visible for the first time, and previously undetectable from inside the tree it was happening to.

**The pid guard compares the full path and not the basename, and the first version did not.** `pipeline_routes.py:_live_pid` is the house pattern and only ever READS, so a recycled pid there is a run wrongly reported busy. `make down` SIGNALS a process group, so the same mistake kills an unrelated process tree — and here it is not hypothetical, because every checkout runs a file called `capture_server.py` and an `npm run dev` under a directory called `app`. A basename check answers *yes, that's ours* for another tree's server.

**A half-started stack is not a started stack, and `make up` reported one as started** (found on the owner's machine 2026-08-30, hours after this entry landed). A bare `make server` held `:8000`; `make up` then started the app, spawned a capture child that could not bind, retried five times, hit the fast-failure cap and stopped. The end state served the app off the SQUATTER — right store, right data, and **no file watching at all**, so a `git pull` would not have been picked up. Everything looked healthy.

**The root defect was the probe: `wait_for_port` asked the SOCKET, not the child.** A port another process holds answers exactly like one of ours does, so `make up` reported the stack up on the strength of the squatter's reply:

    pkmnscan is up
. **A liveness probe another process can satisfy is not a liveness probe** — it now takes the child and returns failure the moment that child is gone.

**The collision itself is untouched and must stay loud.** D43 is why: a server that quietly moved to a free port would serve a DIFFERENT store. What was wrong was never that two things wanted one port; it was that the system settled into a working-looking half of itself and said so. Four guards, none weakening the collision:

- **The probe takes the child**, so a squatter can no longer be mistaken for success.
- **`start()` will not start the app if capture did not come up.** The app alone is not a product, and the half that failed is the whole reason this supervisor exists.
- **A held port is not a retryable crash.** `_refuse_capture` says who holds it and stops; burning five retries and a backoff on a condition that cannot change without a human was the old behavior and it produced the silent end state. `_note_exit`'s retry is for a child that started and died, the opposite case.
- **`make dev` and `make server` refuse while this checkout's supervisor is up**, which is where the squatter comes from. `PKMNSCAN_FOREGROUND=ok` bypasses, the shape `PKMNSCAN_MAIN=off` already uses.

**`make up` preflights the port before spawning anything**, so the refusal costs no processes — and it prints the TAIL of the holder's command line rather than the head, because `ps` leads with a 96-character interpreter path and a head-truncated line identified the process as *Python* and nothing else, on the one output whose whole job is telling you which process to kill.

**`make launch-agent` is not this fix** and was asked about as though it might be. It makes `make up` the canonical starter, so a hand-run `make server` becomes rare — it prevents nothing, and under `KeepAlive` it would restart the supervisor into the same wall.

### The supervisor watches itself

Added 2026-08-30, from the owner asking how they would know whether a change touched `scripts/serve.py` — the one file the watcher did not cover, because it is the watcher. Answering it turned up a worse sibling nobody had noticed.

**`server/ports.py` and `store/files.py` were ALREADY watched, and that made it invisible.** A change to either restarts the capture CHILD — in the log, at the usual speed, looking exactly like the fix landing — while the supervisor goes on running the module it imported at boot, because Python caches an imported module. Something restarts, so nothing looks wrong. The `scripts/serve.py` case at least failed silently in both halves; this one failed while appearing to succeed.

`SELF_FILES` is the four files this supervisor is made of — itself, `envfile.py`, `server/ports.py`, `store/files.py` — and a change to any of them re-execs the process rather than restarting a child.

**`os.execv`, which keeps the PID**, and that is the whole reason to use it rather than spawning a replacement and exiting: `supervisor.pid` stays valid, and launchd sees the same process it started instead of an exit it would race to restart. Children are stopped FIRST, because exec throws away every `Popen` handle — anything still running would be orphaned, holding the ports the new image is about to want. The parse pre-check applies as before; if exec fails anyway the children are rebuilt and the log says the old code is still running.

**The Makefile is not in that set, and saying otherwise was wrong.** It was claimed once in conversation that a Makefile change also needs a restart. Three comments in `scripts/serve.py` mention the Makefile and nothing reads it; `make` re-reads it from disk on every invocation, so it cannot make a running process stale. Corrected here rather than left standing, because a rule that names one file too many is how the real list stops being read.

**`scripts/docs-audit.py`'s `supervisor self-watch` row is what keeps the list honest.** A hand-written list of a file's own imports goes stale the next time somebody adds one, and the failure it would reintroduce is the invisible one above. The row parses `serve.py` with `ast`, resolves its module-scope imports against the tree, and blocks on any project-local import missing from `SELF_FILES`. Mutation-tested: dropping `server/ports.py` from the list takes it red and names the file.

### The screen

**One press fetches and then joins, and the two are reported separately.** `#/runs`' join step carries the control. The fetch draws a receipt naming the file, the rows, the SKUs, the sets and the finishes, and says which games were checked against a previous export and which were not. A fetch that refuses does not join: it wrote nothing, so joining after one would silently re-use the previous export and look exactly like the fetch had worked.

**The join is handed the file by name, not the bytes.** The server already holds them.

**The control that waves a refusal through is absent unless the refusal is one an operator can answer.** `FETCH_ACK` lists the two codes that have an answer, and every other refusal draws its sentence and nothing to press. An expired session, a WAF block and an export for the wrong product line are fixed somewhere other than this screen, so a button there would offer to wave through a refusal the screen does not understand. Absent rather than disabled is D33's rule, for its reason: a disabled button is one attribute away from pressable. Retired 2026-09-02 with the two refusals it listed (D64, amended): every fetch refusal draws a sentence and nothing to press, and `FETCH_ACK` is gone.

**`app/tests/run-panel.spec.ts` asserts that absence at rest and after a clean fetch.** A control appearing once the panel had merely been used would be as wrong as one always there. Two mutations were observed failing: drawing the acknowledgement for every refusal, and joining after a refused fetch.

### What it costs

- **`RunAtLoad` does not survive the Mac sleeping.** A phone hitting a sleeping Mac gets nothing. Inherent to D13, written down now rather than found as a bug in three weeks.
- **An agent session restarts the owner's live server.** With the agent on the main tree, any session editing `store/` or `server/` bounces the server the owner may be capturing with. That is what was asked for, and a further argument for main-tree-only.
- **A request accepted but not yet inside `_dispatch` is uncounted.** Microseconds; closing it means reimplementing `handle_one_request`. Recorded in `docs/DEBTS.md`.
- **The swap gap.** Tens of milliseconds of `ECONNREFUSED` between children, which the client surfaces as `unreachable` because it deliberately has no retry. The fix, named and NOT built: the supervisor holds the listening socket and passes it to the child. Rejected for v1 because it turns a fast honest refusal into a hang when the new child fails to boot.

**D13 is not reopened.** The store, the photographs and the truth stay on this Mac. LAN reach is the tunnel case D13 already names as needing no code change, and the owner deferred off-site access to its own decision.

**What would reopen this: the watcher restarting during real capture work.** If the server bounces under the owner mid-box because a session saved a file, the answer is not to weaken the drain — it is that the agent and an active feeder run should not share a tree, which is one condition on `is_linked_worktree` away from what is already built.

---

## D54 — A re-emit adds; it never subtracts

**Built 2026-08-30, and it was a live data-loss bug that every check in this repo passed.** Pressing `emit` twice on one run destroyed its output: the good `import-listed.csv` was overwritten with a **header-only file**, and `manifest["emitted"]` was rewritten as `{"listed": [], "sub_threshold": [], "pushed": 0, "pushed_skus": 0}` — after which `reconcile` refused **"this run has emitted nothing — run `pkmnscan emit` first"** on a run that had emitted perfectly an hour ago, with its CSV already imported to TCGplayer.

**The mechanism, because it is one line and three instances.** `cli/cmd_emit.py:_game_only` derived its SKU set from PRICES, which do not change between emits, while `pipeline/join.py:import_rows` drops every SKU whose `add_to_quantity` is 0. `_write` then decides whether to open a file **from that set**, and `tcgcsv.render` emits the header before it iterates rows — so an empty row list produces a valid CSV of nothing, on top of the file the operator was told to import.

**Three things drop a SKU after `_game_only` and it knew about one:**

1. a **withheld** SKU (D49) — subtracted since 2026-08-29, which is the instance D49 closed;
2. a **`no_market_data` SKU answered `"unlisted"`** — `prices_for` drops it and nothing subtracted it. **This one fires on a FIRST emit**, for a game whose only above-threshold entries are unpriced-and-unlisted;
3. **`add_to_quantity == 0`**, every copy already committed — which is every SKU on a re-emit, and is the one that destroyed the file.

A fix that special-cased the third would have left the second standing. **So the rule is stated over the class:**

> **`emit` never opens an import file for writing until it has at least one row for it. What it writes is always the DELTA — the copies not already sent — and it says so.**

`_game_only` now takes `prices_for`'s own output and intersects it with the matches whose `add_to_quantity` is above zero. That set is *by construction* the row set `import_rows` will produce, so `only` stopped being an estimate. `pipeline/join.py:write_import` is split out of `emit_import` so rows can be looked at before a file handle opens; `emit_import`'s signature and behavior are unchanged, because T3 calls it in six places.

**Rewriting the file identically was considered and is refused, and this is the load-bearing half.** To do it, `emit` would have to exclude this run's own contribution from `cli/resolve.py:_committed_keys` so its copies became uncommitted again — which is exactly the state that produced the Gate B defect this repo already paid for, where a post-import re-emit **re-counted 37 copies into the files**. TCGplayer's Import to Staged *adds* quantity, so a file repeating already-imported rows double-stages them, and **nothing in this pipeline can know whether the operator imported the first file.** That is `reconcile`'s job and it is D34's argument: no export this pipeline reads can assert what TCGplayer is holding.

**No refusal. Exit 0.** `emit` is documented free and re-runnable and T7 calls a re-emit *"the ordinary thing to do after editing a review"*; a non-zero exit becomes `ok: false` on `POST /pipeline/runs/<name>/emit` and would draw a failure for a run in a perfectly good state; and a refusal is the "emit once, ever" outcome that the legitimate cases — lifting a hold, answering a `no_market_data` SKU, setting `sub_threshold` — all forbid.

**The no-op branch says the thing the operator needs, and nothing else did.** An operator who changes `sub_threshold` from `"floor"` to a flat price after emitting and presses again used to get a destroyed file and a cheerful summary. They now get told, in words, that every copy this run matched is already at `pushed`, that the file is unchanged from the earlier emit, and that **a price changed after an emit cannot travel this road** — the copies have already been sent under the old answer. It does not print `next: import`, because there is nothing new to import.

**`emitted` is a union across emits, via a named `Run.record_emit`.** `Run.set` stays replace-not-merge — `set(collected=…)`, `set(joined=…)` and `set(batch_ids=…)` all depend on that, and a global merge would be a wide silent change for one field's problem.

**The union is not tidiness, and `reconcile` is why.** It passes these SKUs to `join.reconcile_import`, which reports in **both directions** — so after emit → import → re-emit → import, a record holding only the last delta puts every SKU from the first import into `rows_without_cards`, and reconcile prints *"something else wrote it"* about rows it wrote itself. `pushed` accumulates because it is a quantity of copies and quantities sum; **`pushed_skus` is DERIVED from the lists rather than accumulated beside them**, so it cannot come to disagree with them — D49 Part One's rule applied to this record. A SKU withheld *after* being emitted stays in the union, deliberately: it was sent, its copies are at `pushed`, and the staged export will carry it.

**`_phase` is hardened independently, and that is belt to this braces.** It tested the `emitted` dict for truthiness, and `{"listed": [], ...}` is a truthy dict — so a run whose record had been blanked read `reconcile` on the panel while `reconcile` itself refused. It now asks whether the record names a SKU, through `Run.emitted_skus`. **No run on disk was ever in the corrupted state, so there is no migration** — but a hand-edited manifest, or one written by an older checkout, must not send the operator to a step that will turn them away.

**The T7 assertion that guarded this never measured its own message, and that is the finding worth more than the fix.** It read `len(read_export(IMPORT_LISTED).rows) == 0` under the message *"the file holds no zero row"*. **"The file holds 0 rows" is satisfied identically by the emitter correctly omitting a zero-quantity row and by the emitter overwriting two good rows with a bare header.** A test whose pass condition is met equally by a behavior and by that behavior's catastrophic opposite is not testing the behavior, and the destruction lived behind it for as long as it existed. T3 carried the same blindness in its full-cycle case.

Both now assert **byte equality of the file across the two emits** — byte and not row, because a rewritten empty file is a valid CSV of nothing and a row count cannot tell that from the rows never having existed. The original no-zero-row claim is kept and asserted where it is observable.

**And nothing had ever asserted the manifest after a second emit.** That is why this survived: every assertion in T7's re-emit block was about the STORE, and the store side was already safe — its idempotence lives in `cli/resolve.py:_committed_keys` and was pinned. The record beside it, which `reconcile` reads, was pinned by nothing. It is now, along with the end-to-end nobody had written: `emit → join → emit → reconcile`, **which would have caught this in one line**.

**Observed failing first, six assertions**, before a line of `cli/` was touched: the file's bytes (three lines to one), the surviving quantities, the manifest's SKU list (`[]` against both), the `next: import` line still telling the operator to import a file just destroyed, `reconcile` exiting 1, and the copies never reaching `staged`. The union was separately mutation-tested by making `record_emit` replace rather than merge, and it went red naming the delta alone.

**What would reopen this: a staged quantity `emit` could read.** The whole reason a re-emit may not rewrite the file is that nothing here knows what TCGplayer received. If `reconcile` were ever pointed at a fresh Export From Staged and allowed to set counts absolutely — the change D34 names and nobody has argued — then `emit` could compute the true outstanding delta per SKU rather than inferring it from `_committed_keys`, and rewriting the whole file would become the honest thing to do.

---
## D55 — A set code the model glued on is removed by shape, and only after the key has missed

**Built 2026-08-30, from the owner reading their own review queue three times in one afternoon**: *"The number read as UNL / 120/219, which is in no row"*, then the same sentence for `UNL - 060/219` and `UNL - 150/219`. Each card matched by name and each was therefore queued rather than listed, and each one's row was sitting in the export it was joined against.

**The read was not wrong about the card. It was wrong about the field.** `identify/prompt.py`'s Riftbound contract says in as many words *"Do not add a set code printed elsewhere on the card"*, and the model added it anyway — on top of digits it had read perfectly. Rengar, Trophy Hunter is `120/219` in the export and `120/219` is what the photograph shows; what arrived was `UNL / 120/219`, which is in no row because no row is spelled that way.

**Measured, the rate is an order of magnitude worse than the run this mechanism was built from.** Run `2026-08-29-box1-01`: 3 of 133. Run `2026-08-30-box3-01`: **7 of 39**. And the same card was read both ways in one box — `UNL • 198/219` at card 3, `UNL - 198/219` at card 31 — which is the finding that decides the whole design: **the separator is arbitrary**, so enumerating separators is a losing game.

**D46's `_strip_set_code` COULD NOT BE WIDENED TO COVER IT, AND THAT IS WHY THIS IS AN ENTRY RATHER THAN A LINE OF CODE.** It was a tuple of two characters — bullet and middle dot — and an `rsplit` over them, licensed by the measurement that no export cell contains either. Adding `-` and `/` to that tuple is not a bigger version of the same repair, it is a different and destructive one: `rsplit("/")` over `120/219` yields `219`, a real identifier belonging to another card. A character-based rule cannot reach the observed shapes without eating the field it exists to repair. D46's own docstring predicted this class and declined it pending evidence — *"the evidence to check first is whether the remainder still parses as an identifier"*.

**So the rule describes a set code instead of a separator, anchored to the front: two to five letters, no digits, then one separator.** Measured against every distinct `Number` cell in both games keyed this way — **1,237 Riftbound and 396 One Piece** — it matches **zero** of them, which is the same license the old tuple had, taken over a shape rather than a character. Three bounds do the work and each is load-bearing:

- **Letters only.** `T02 // T03` is a real double-sided token, 13 cells carry the form, and the prompt asks for the spaces around its `//` by name. Its first group has digits, so it is untouched — and it is exactly what a slash rule would otherwise have had to reason about. `SP3/006` and `303*/298` are excluded the same way.
- **At least two.** One Piece prints **16 cells as `P-044`** — one letter, a hyphen, digits. A bound of one strips every one of them to a bare number. This bound is the reason one rule is safe for both games instead of a rule per game.
- **At most five.** Nothing measured needs more, and an unbounded run of letters starts eating names the day something hands this a title by mistake.

**And it moved out of the key builder into the ladder, which is the stronger half of the safety.** `_strip_set_code` ran inside `_key_printed_code`, so every identifier was rewritten on its way to the lookup whether or not the raw one would have matched. `_repair_set_code` is now `pipeline/join.py:_walk`'s **second rung**, asked only when the key found no rows — so a card that joins cleanly is never handed to it at all, and no repair can move a card that was already joining, **however a future export's cells are spelled**. It is D35's own rule for D35's own rung, applied one step earlier: it fires only on an empty result, and the worst a wrong repair can do is miss again and fall through to precisely where the card was already going.

**`KeyStrategy` GAINS `repair`, WHICH IS WHY THIS IS ONE RUNG AND NOT THREE COPIES OF ONE.** D35's whole entry is about the ladder being written once with the per-game part as a value; a repair bolted into one game's key builder would have recreated the shape that let D35's own rung land in Pokemon and not in Riftbound. `pokemon` and `pokemon_code` declare no repair, so nothing about their walk changes.

**It reports itself as `code~:` RATHER THAN `code:`, AND THE SEPARATE LABEL IS THE POINT.** This is a count of how often the model ignores an explicit instruction in its own prompt, and a repair that reported an ordinary match would make its own cause invisible on the run report — the rate would only ever be discoverable by someone re-reading raw identifications. Same argument D35 makes for spelling its rung `name?:` rather than `name:`: two facts with two remedies get two strings. **It does not reach the queue entry**, for the reason D35 already records — `QueueEntry` declares no `lookup` field — and it does not need to, because a repaired card no longer queues.

**What it recovers, re-walked over the real runs rather than estimated.** Box 3: all 7 glued reads now join by exact number, at **$30.81, $23.76, $17.06, $12.52** and three more — cards that were sitting in a queue offering one name-matched candidate the operator had to answer by hand, one at a time, on every future join. The 2 that remain on the name rung are the reads it must not repair: `044/106` for the export's `044/166`, a digit misread, and one blank number. Box 1's 133 cards are unchanged — 129 clean, the 3 bullet cases still recovered, and `Wuju Master` still correctly finding nothing.

**Recovering the number is better than falling back to the name, which is the whole reason to spend an entry on cards D35 already rescues.** The name rung deliberately only ever QUEUES (the owner's ruling in D35), because the field that tells one card from another is the field that could not be read. Here it *was* read — correctly — and something else was added to it. A recovered number is an exact join and lists the card.

**What would reopen this: the rate not falling, or a fourth separator that is not a separator.** The repair makes the defect free rather than absent, and `identify/prompt.py`'s instruction is still being ignored 18% of the time on this set. If `code~:` keeps climbing, the fix is upstream in the prompt — D46's own closing rule, that a repair used on cards a better read would have handled means the read is what to fix. What this rule genuinely cannot reach is a set code the model writes with no separator at all (`UNL120/219`) or one that is not letters-first; both would need the remainder checked against the catalog rather than against a shape, which is a different and much bolder rule than this one.

---


## D56 — A run names the drawer it was over, and the name is joined at read time

**Every run on the wire carries `box` and `box_name`, joined from the registry at read time and never written into the run directory.** Built 2026-08-30, from the owner looking at `#/pricing`'s run picker: it needed the name they gave the box, not just the date and the raw number.

**The store had been holding the answer since D20 and no surface that lists runs had read it.** That entry makes a box an object with a name, makes the name unique, and makes it *how a box is addressed* — the capture screen's Box field searches on it, `#/inventory` draws it beside every position, and `#/runs`' own box picker one panel up draws `Box 3 · RB Epics`. Meanwhile every surface that mentions a RUN drew a digit: the pricing picker chip said `2026-08-30-box3-01` over `15 SKUs`, `RunPanel`'s run rows said `box 3`, and the cart leg above the spend button said `Box 3`. Measured on the owner's own store, the three names those screens could not say are `UNL Rares`, `ME01 C/UC` and `RB Epics`.

**The join is the server's, and it happens on every read.** `server/pipeline_routes.py:_summary` sends two new fields on every run: `box`, from `_run_box`, and `box_name`, from `_box_names()` — the box registry, parsed fresh out of `inventory.json`.

**Nothing is stored on the run, and that is the load-bearing decision.** The obvious cheaper design is to have `identify` write the name into the manifest at spawn time, and it is wrong for D20's own reason: a rename is a live edit that relabels every card in the box on every screen that draws one, and `cli/runs.py` makes a run an **immutable input** precisely so a batch can outlive the server that started it. A name copied into a run directory would be a second answer that can never be corrected — the run would go on saying `RB Epics` after the drawer became `Riftbound epics`, with no way to fix it short of editing a manifest by hand. T7 asserts the rename reaching the run on the next read, which is the case a stored name fails.

**It parses the inventory and not the snapshot, and it is one read for a whole list.** `GET /pipeline/runs` is the polled route — 4s while anything is live — so `_box_names()` is called once and passed into every `_summary`; the single-run routes have nothing to share it with and read their own. Measured on the owner's store: `Inventory.parse` over 715 cards is **4.5ms**, against **7.3ms** for `Store().read()`, which also parses a 268KB identification cache and both queue files that nothing here reads. Cheap either way; the cheaper one is what a poll should take.

**It never raises.** `do_status`' rule applied to a decoration: a store this cannot read costs the run list its box names and must not cost it the run list, which is where the phase, the elapsed time and the download links are.

**And it deleted a second implementation of `_run_box` in TypeScript.** `RunPanel.tsx:boxOf` derived the box itself, with `/box(\d+)/` over the whole capture path where the server anchors `^box(\d+)` on its **basename** — so a parent directory with a number after `box` in its name would have answered differently on the two sides, and the symptom would have been a run filed under the wrong box and nothing else. It agreed on all four runs on this machine and was one oddly-named folder from not agreeing. `app/src/runScope.ts` is now the one module, `boxOf` prefers the server's field, and the old derivation survives only as the fallback for a payload that predates it — this response is cast rather than validated, the shape `written_at` already takes for the same reason. **Two of the owner's four runs carry no `scope` block at all**, so that fallback is not hypothetical: `pkmnscan identify captures/cards/box3` writes none.

**Both halves, never one.** `CLAUDE.md` is explicit that the name travels *beside* the number rather than replacing it, and both are load-bearing: the name is what the operator recognizes, and the number is the shelf they walk to, the capture directory the photographs are in, and what every refusal in `server/pipeline_routes.py` says. **An unnamed box draws the number ALONE** — no separator and no placeholder — because D20 leaves a name optional, so unnamed is an ordinary box and `Box 9 · —` would draw a fault where there is none. Same for a box that has since been deleted (D10 ruling 3): the run remembers a number the registry no longer has, and the number by itself is the honest rendering.

**The pricing chip leads with the box and keeps the directory beneath it.** That is `docs/DESIGN.md`'s human-label-large, machine-string-small rule — which the review queue already applies to its reason codes — pointed at a picker: the box is what a person is choosing between and the run directory is the greppable identity of the thing they are choosing.

**The run name is not demoted out of usefulness, and that was the one real risk in the re-order.** Box 1 carries **two** joined runs on the owner's store, so two chips draw the identical headline `Box 1 · UNL Rares` and the date beneath is the whole of the difference. It therefore stays in the utility face at the metadata size rather than dropping to the 10px a count can afford, and the gap beside the count is `--s3` rather than `--s2`: both facts are mono, and the worst adjacency is two runs of digits — `2026-08-30-box3-01` ends in `01` and `15 SKUs` opens on `15`. The chip grew by **1px** for it, which is the owner's *at no cost* satisfied literally.

**No interpunct between them, and that is D41 rather than a preference.** That entry answered this exact question for `.boxops-meta` by giving the facts structure instead of dots. Line one of the chip already spends the one dot it can afford.

**Where else it lands, and the cart is the one worth arguing for.** `#/runs`' run rows and its one-box scope line, and — from the cart rather than from a run — the leg head above the reading picker and the per-box row of the cost breakdown. D33's money gate is two presses over a number the operator cannot miss, and until now the row that decides what reading a box costs could only call that box by its digit, on the one screen in the product that spends. **The multi-box scope line deliberately does NOT name them**: it would run the header to two and three lines while the picker directly below draws every box named.

**The name is drawn and never sent.** `CartBox` gains a `name`, and `RunPanel`'s `legs` projects a cart row to what the route reads — which does not include it. That is not tidiness: `scopeKey` is built from `legs` and is what **voids the estimate**, and renaming a drawer changes not one byte of the send. An estimate retired by a rename would be the money gate crying wolf.

**Two sources for the name, with a stated precedence, and they cannot disagree.** The run rows read it off the run (the registry, server-side); the cart legs read it off the picker's own `GET /boxes` (the same registry, one route over). A cart row is a box the operator just chose and no run over it may yet exist, so the run list cannot answer for it. On `#/pricing` the same split appears one scale down: `scopeName` prefers `detail` over the list row, because `runs` is fetched once at mount while `detail` is re-read by `load()` and therefore by **Reload** — so a box renamed on `#/inventory` reaches the header on a press rather than on a page reload.

**Covered in both places, and mutation-tested in both.** T7's `check_pipeline_routes` holds the server half: a box the registry has never heard of reports no name, naming it names the run without the run being touched, a **rename** reaches it on the next read, a run with no scope block is still placed and named off its capture directory, and the list carries it too. `app/tests/run-panel.spec.ts` and `app/tests/pricing.spec.ts` hold the client half. Five mutations were observed failing before the cases were kept: `boxLabel` ignoring the name; `boxLabel` drawing `· —` for an unnamed box; `boxOf` dropping the legacy derivation; the pricing chip reverting to the run name alone; and the chip dropping the run directory, which the two-runs-on-one-box case exists to catch.

**What would reopen this: a box name long enough to wrap a run row.** These are three short labels on one store and nothing truncates. If a name ever pushes `.run-row`'s third column onto a second line, the fix is an ellipsis on the scope cell — `.run-row-name` already has one — and not dropping the name.

### Three fallbacks were deleted the same day, and they were worth zero

`boxLabel` returned `string | null`, so every call site had to answer for a null box. Three did, three different ways: `?? Box ${box}` on the cart leg head and the scope line, a lowercase `?? box ${box}` on the console label, and — on the per-box row of the cost breakdown — nothing at all. That last one was found by mutation and reported as a reporting defect on the money screen: `boxLabel(null, …)` returns null, and a null JSX child renders as an empty term above the control that spends.

**The other two were no better, which is what decides this.** Run against a null box they render the literal string **`Box null`** and **`box null`**. They read as defensiveness and were noise: **there is nothing honest to draw from a box number the server failed to send.** So all three are gone and `boxLabel` gains an overload — a real `number` returns a `string` — which leaves one shape at four call sites instead of four answers to a question none of them can be asked. Every one passes a number the types already guarantee: `CartBox.box` and `RunScope.box` are both plain `number`.

**The overload is not a compile-time proof, and the first draft of this paragraph said it was.** Removing the signature produces no type error anywhere — JSX renders a null child as nothing and a template literal stringifies it, so both shapes these values arrive in swallow a null silently. Corrected here rather than quietly softened, because the wrong version would have a later session trusting `tsc` to catch a class of defect it cannot see.

**So the fix is at the source and not at the four draw sites.** `_resolve_scope`'s ticked-selection branch was built five times in T7 and read back zero: every other `indices` payload there refuses — an empty array, a bad member, a card with no photograph, and the cart case that exists to prove leg two's bad flag tears down leg one — so the dict it returns was never asserted. Nulling its `box` left `make harness` at 7 of 7 and `npx playwright test` at 224 passed. T7 now sends a selection preflight that SUCCEEDS and asserts all three fields; all three mutations — `box` to null, `whole_box` to true, and `cards` counting the directory rather than the selection — were observed failing against it.

**It is not the double-click guard, which is the tempting guess and is wrong.** `_run_box` reads the scope block first and falls back to the capture directory's name, and a scope directory is called `box3-1-<stamp>` — so `^box(\d+)` still answers 3 and `_busy_run` still fires. `box_name` goes through `_run_box` too. What a wrong box costs is the preflight RESPONSE, which `RunPanel.tsx` reads with no fallback: the per-box cost row, each leg's React key, each console label, and `_preflight_total`'s `busy` list. D33 makes that the one screen whose numbers must be unmissable.

---
## D57 — The sale is one press, and the button becomes the way back

**Mark-sold writes on one press, and the row's control becomes `Undo` for twenty seconds.** Built 2026-08-30 on the owner's instruction, on `#/inventory` only.

**This honors `docs/DESIGN.md`'s headline rule rather than carving an exception out of it.** That file bans a confirm dialog on a reversible action and has specified one-tap mark-sold since it was written. A sale is the most reversible write in the product — one route, two directions, no expiry, no listing hold — and it was the only one carrying a modal. D28 fixed the same asymmetry from the other side by giving the review answer an undo; every guard D28 added stays.

### The modal's photograph was redundant

`Inventory.tsx`'s panel confirmed identity rather than intent, and said so in its own comment: the question was *is the card in your hand the card at this position*, which only a photograph answers. D38 overtook it by drawing the selected copy's photograph at 449x627 on the same screen.

- **Exact** for the row the walk points at (`aria-current`) — same bytes, same position, one panel over.
- **Approximate** for a second copy of the same SKU in another box: same card face, different slot. D45 makes that copy's own photograph one press away, because the position label is a control that walks the browse to it.

The check is demoted from mandatory to available, not deleted.

### Undo appears twice, and the second one is not redundant

| site | why |
|---|---|
| the row's slot | where the press was and where the eye is |
| the screen receipt | the only one that survives unmount, and the only one that can explain a refusal |

Copy rows unmount on three paths — stepping the walk, a query matching nothing, and a failed re-read, since `useSearch` clears its results on failure. The twenty-second clock stops for none of them, which is why `Inventory.tsx` and `BoxBrowse.css` have both argued that the promise has to outlive the list. `app/tests/inventory.spec.ts` asserts it by selling a copy and then stepping the walk.

`already_sold` and `sold_origin_unknown` return `canUndo: false`, so the row draws the plain word `sold`. The sentence saying why there is no way back needs prose, and a 32px slot has none.

**Accessible names differ deliberately:** the receipt's is `Undo <place>` and the row's is `Undo the sale at <place>`. Identical names would leave a screen reader unable to tell one sale's two ways back from two different sales. The visible word is `Undo` on both.

**No `Retire` sits beside it**, because the server refuses to retire a sold card and the control could only fail.

**It renders inside the `sold` branch, which is forced rather than stylistic.** `doSell` sets the optimistic `soldKeys` overlay in the same continuation as the receipt, so the next render is already past the sold guard and a branch above it would be unreachable.

### Retirement is unchanged, and the asymmetry is the ruling

D26's write keeps its panel, its photograph and its receipt-only undo. A retirement without a reason is refused (`retire_reason_invalid`), so its four reason buttons are the write's only input rather than an acknowledgement to dismiss. This entry removed a press that asked an already-answered question; that panel asks one with four answers.

### Overshoot

**The guard is `busyKey` and nothing else**, which is the owner's choice over displacing the control. `Fulfillment.css` records the opposite ruling for the same failure one screen over, and it was earned: `Pull` and `Mark sold` occupied one position one state apart, so a double-tap sold a card whose photo was never seen. `app/tests/fulfillment.spec.ts` measures those two rectangles.

What covers it here, in descending order of worth: every control in the slot is disabled while a write is in flight and `doSell` returns early besides; the slot shrinks to one right-packed control, vacating the coordinate `Mark sold` occupied; and a receipt appearing above pushes the copies list down. **What does not cover it is the busy gate**, which against a local server reopens in milliseconds and does not span a human double-tap.

**Two residual risks, named so they are not found as surprises.** `Mark sold` is an ordinary `<button>` in the tab order, so Tab-then-Enter now writes where it used to open a modal, and a held Enter can oscillate sell to `Undo` to sell. Neither is reachable from a key binding: `BoxBrowse`'s window handler navigates and writes nothing, and `App.tsx`'s leader chord only sets a hash. The slot's two-controls-to-one change replaces the DOM node, so focus falls to `<body>` and a held Enter stops; the arrow keys still walk, because that listener is on `window`.

### Consequences

- **It overturns `docs/specs/order-flow.md` §13**, which forbids a second sale path without both guards. One guard is dismissed on the owner's ruling, and §8.1's argument survives intact: the guards belong to the write rather than to the Fulfillment view, and nothing in D5 says the owner may have the write without them. `#/fulfillment` is untouched, per D31.
- **It is a client change only.** `POST /inventory/<box>/<index>/sold` already took `{}` and `{"undo": true}` on one path and already answered `restores_to`. Store, harness and every Python test are unaffected.
- **The accent fill left the screen with the panel**, and `Inventory.css` records why. `docs/DESIGN.md` says where a fill may go, never that a screen must have one; `#/runs` draws none either.

**The change was makeable with every check green, which is worth more than the feature.** `app/tests/inventory.spec.ts` asserted only that `Mark sold` and `Retire` were visible and never pressed either, so the confirm panel, the receipt, the undo window, `canUndo` and the `already_sold` path were entirely unasserted, and `open()` did not even stub the sale route. Six cases now cover it. Three mutations were observed failing before they were kept: dropping the `canUndo` filter, never drawing the row's `Undo`, and a press that writes nothing.

**What would reopen this: a sale recorded against a copy the owner did not mean.** The fix to reach for is `.fulfillment-step`'s displacement, not the panel this replaced.
---

## D58 — A card's number counts the cards in the box, not the slots

**A card's number counts the cards in the box, so selling one makes the card behind it take that number on every screen.** Built 2026-08-30 on the owner's instruction: when cards are marked sold, the slot is not left empty — the cards before it move up one.

**It is the answer to D30, which had been waiting on the owner since 2026-08-23.** That entry states the problem in the sentence this one deletes: `Card 17` is the **seventeenth slot**, not the seventeenth card you can count, and once a section has holes those two stop being the same number and every label in that section becomes uncountable by hand.

D30 answered it with `neighbors` and `section_gaps` — built, and both kept — and with a physical marker for the emptied slot, which was the owner's open item and is now moot: there is no gap left to mark. Its box-audit paragraph gets easier for the same reason, because what is in the section and what the record says are the same count again.

### Two things are wider than the ask, and both are the owner's

**The stored index never moves; the LABEL does.** The instruction says to assume the indexes can move, and D10 as amended already carved the seam this uses instead — *positions are never renumbered* governs the INDEX, and the label is a view — restated in `pipeline/join.py:Position`'s own docstring. Moving the stored index was costed and rejected on four measurements, each a reason not to reach for it later:

- **`do_remove_card` deletes its target and a sale must not**, so a sold record's index has nowhere to go once the survivor above slides into it. Every answer is a v3 schema, rewriting `next_index`, `box_fill`, `copies_on_hand`, `positions_for_sku`, `_walk`, `_release_plan`, the box-delete gate and the migration.
- **The Fulfiller's twenty-second undo would aim at the wrong card.** `undoSale` posts to `/inventory/<box>/<index>/sold` — a POSITION, with `SOLD_FIELDS = ("undo",)` and no aim check — and after a shift that position holds his next card.
- **D28's answer-undo and D37's stand-down reversal would stop working.** `_answer_before` and `_clearing_event` treat a `renumbered` history line as a hard stop, and every sale would write one.
- **D52 would gain a fourth occupant-changing operation**, on six screens whose `photoUrl` callers rest on the element re-keying when a card moves.

**Sealed boxes consolidate too, so there is no open/sealed distinction at all.** The ask gated this on the lid; the owner dropped the gate when shown that the alternative makes every label jump the moment a box with sold cards is sealed. What it costs is named in D20 below: a sealed box's denominator moves now, which that entry froze `capacity` to prevent.

### What it is, measured

On the owner's store the day it landed:

| box | state | records | sold | retired | holds |
|---|---|---|---|---|---|
| 1 · UNL Rares | open | 133 | 2 | 0 | **131** |
| 2 · ME01 C/UC | sealed | 543 | 0 | 1 | **542** |
| 3 · RB Epics | open | 39 | 9 | 0 | **30** |

Every label above a departed card moved once, deliberately — the same event as D10's deletion of automatic sectioning on 2026-08-29, and pinned the same way, so the next such shift cannot be accidental either.

**`Position` gains the box's occupancy and stays the only label formula in the repo.** `occupied` is every on-hand index in the box, ascending, and `departed` is every terminal one. `slot` is this card's place among the first; `section`, `section_start`, `section_end` and `card` all read it. **`None` and `()` are opposite facts and the sentinel is `None`**: an empty tuple is a box every card has left, whose cards must still render as departed rather than reverting to slot numbers, and `None` is a caller with no inventory to consult — which renders in index space, byte-identically to the day before this landed. `BoxView` is that pair with a name and `BoxView().at(box, index)` is the one constructor.

### The sections adjust, and that is what makes both numbers countable

**Mapping the cards and not the dividers would have been a half-build that looks right.** A divider declared at index `s` stands in front of the first card still on hand at or above it, so its number is the count of cards below `s` plus one. Both `slot` and `section_start` then move by the same amount for a departure in an earlier section, and `card` — their difference — does not. Worked on box 2's real layout `[1, 86, 171, 253, 394]` after four cards depart at 10, 20, 30 and 180:

| | before | after |
|---|---|---|
| divider numbers | 1, 86, 171, 253, 394 | 1, **83**, **168**, **249**, **390** |
| the card at index 200 | `Section 3 · Card 30` | `Section 3 · Card 30` |

It becomes `Card 29` only when 180 sells, which is a card in its own section and in front of it. *Go to the third divider and count twenty-nine cards* — and a sale anywhere else in the box does not disturb the count. T7 asserts both halves, because a build that mapped nothing passes the second and a build that mapped only the cards passes the first.

**An empty section keeps its number.** Two dividers with no card left between them map to one number and are deliberately not deduped: the plastic is still in the box, and renumbering the sections behind it would send a person to the wrong divider. `sections_detail` reports it with `count: 0`.

**A divider past the fill keeps its unfilled slots, and a T7 case caught the version that did not.** `[1, 51]` typed into a five-card box means section 2 starts at the fifty-first CARD, and answering *the sixth* would quietly delete a plan. `Position._divider` adds one for each slot between the box's high-water mark and the divider, so the two definitions agree everywhere inside a box that has grown into its own dividers.

**The stored layout is still in index space and is never rewritten.** Same argument as the index itself: a divider list rewritten on every sale is an answer that can drift and that nobody can correct. Only the rendering maps.

**So the dividers editor moved to count space**, and this is the piece the owner's own question exposed. `BoxOps.tsx` seeded the field from the raw `record.sections` and posted the same list, so under this change an operator would have been typing index numbers that appear nowhere else in the product. It seeds from `sections_detail[].start` now, and `do_put_box` maps what comes back through `join.divider_index` before `check_sections` sees it. **`divider_index` answers the index of the card the section starts at** — which is what `open_section` already writes when the operator presses `S` at the box, so a divider typed in and a divider put in at the feeder are the same kind of number. **Ordinal 1 is always index 1**, even where card 1 itself has sold, because `check_sections`' rule is a fact about the front of a box rather than about its contents. Property-tested over 4,000 random boxes: the round trip is exact and the result is always sorted, unique and starting at 1.

### A departed card is in no slot

**It does not keep the number it held**, because that number belongs to the card that closed up behind it, and answering it would send a person to the wrong slot. `join.departed_label` renders `Box 3 · departed`, beside `pooled_label` in the same file for the reason that helper's own comment gives: the string that REPLACES a label belongs next to the label formula.

**It names no door.** `sold` and `retired` are different departures with different reversals and both are already on the record beside this string. A second spelling of the state inside the one label formula is what `pooled_label` refuses one paragraph up.

**Its section stays.** The numbers go and the section does not: a departed record belongs to a real part of a real box, the walk groups by it, and nulling it would file every sold card under a third heading that is not a section.

**A receipt is untouched and must stay so.** `Inventory.tsx` and `Fulfillment.tsx` both snapshot the label BEFORE the write, so *Sold Box 3 · Section 1 · Card 7* still names where the operator just was. The departed string is for the record afterwards, not for the moment.

### The denominator follows, which amends D20

**`_denominator` is retired and the answer is the cards on hand, sealed or open.** Forced by the numerator rather than chosen: `slot` counts cards, so dividing it by a frozen capacity draws a card at a percentage of a box it is not at, drifting further wrong with every sale. On a 543-card box that has sold 200, `#100 of 543` puts a thumb a third of the way from the card.

**What the function bought is now held structurally, which is stronger.** It existed so two renderers could not disagree; `_Places.view` computes the count from the walk it already runs and `_box_row` reads it off the SAME instance. One scan, two renderers, nothing to keep in step.

**`capacity` keeps its D20 job and loses this one.** It records how full the box got. `GET /boxes` still reports it, `close_box` still freezes it at the high-water mark, and the seal control still names that number before it is pressed — what it no longer is, is what anything divides by. A sealed box's identity line carries both (`542 of 543 sealed`), because one of them beside a bar reading `#40 of 542` would be the second-renderer failure with two numbers instead of one.

**`GET /boxes` gains `on_hand`**, and `fill`, `next_index`, `cards`, `sold` and `retired` are untouched — `BoxOps` promises its census greps to `inventory.json` and it still does.

### A live defect this forced, and the rule that fixes it

**`store/queues.py:QueueEntry.label` is a stored rendering and nothing had ever recomputed it.** Written once by `cli/resolve.py` at join time, served verbatim by `GET /queues`, drawn by `ReviewQueue.tsx`. Measured on the owner's real store: **15 of 92 entries carry a label drawn against `CARDS_PER_SECTION = 25`**, the divider rule D10's amendment deleted on 2026-08-29. Box 1 declares no dividers at all and its queue holds both `Box 1 · Section 1 · Card 108` and `Box 1 · Section 5 · Card 18` — a section that does not exist.

**It is latent rather than live today, and saying so is the point of measuring it.** All 92 of those entries are `cleared_by_human`, so `open_entries` serves none of them and nothing has been drawing a wrong label on screen. What the measurement establishes is the SHAPE: the field is a rendering that was written down, nothing has ever recomputed it, and a rule that moved left it behind. D28's `Queue.reopen` is the path that would surface one, and the next join writes fresh entries that go stale the next time a layout changes.

**Re-rendered through the fix, 74 of the 92 come out differently** — the 15 stale ones, the retired card at `2/95` which is now `Box 2 · departed`, and the rest renumbered by the cards that have left in front of them.

**D56 states the fix for exactly this shape one register up**, about a run's box name: never write down an answer nobody can correct; join it when it is read. `do_queues` re-renders the label from the live inventory through the same `_Places` every other screen uses. The stored field keeps its value on disk so nothing already written moves, and no route serves it.

**And `cli/resolve.py` built every `Position` with no layout at all**, which is older than D58 and is fixed with it: a box-2 queue entry was written as `Section 1 · Card 300` where the app rendered `Section 4 · Card 48`. Two renderers, two answers, and nothing had ever compared them. `box_views` is that walk, and **T7 asserts the two spell one address on a real card** — the same shape `make port-agreement` uses for the other pair that has to agree.

### The same defect at a second site — `pricing.json` (amendment, 2026-08-30)

**The queue was not the only stored rendering, and `pricing.json` is the one that was on a screen.** `cli/cmd_join.py:_pricing_table` writes `{"box", "index", "label"}` per matched SKU, `GET /pipeline/runs/<name>/pricing` served the stored string verbatim, and `app/src/Pricing.tsx` drew it into `.pricing-photo-caption` under the copy's photograph. Found by sweeping for the shape the section above describes, not by a failure.

**Measured on the owner's store, both runs that have a pricing table:**

| run | positions | unchanged | departed | renumbered |
|---|---|---|---|---|
| `2026-08-29-box1-01` | 113 | 4 | 18 | 91 |
| `2026-08-30-box3-01` | 33 | 0 | 20 | 13 |
| | **146** | **4** | **38** | **104** |

Box 1 holds 133 records with 18 sold, box 3 holds 39 with 24, and neither declares a divider — so all 104 are cards that closed up over a departure in front of them and all 38 are copies pointed at a slot they have left.

**This one was LIVE where the queue's was latent.** Those 92 entries were all `cleared_by_human` and `open_entries` served none of them. All 146 of these are served the moment either run is opened, under a photograph `photoUrl` addresses BY SLOT — so the picture was always the index's current occupant while the caption was the join's, and nothing on the screen said which was which.

**Same posture: re-rendered at read, file untouched.** `server/pipeline_routes.py:_relabel_positions` composes against the live store on every request and serves the stored string never; `box` and `index` travel exactly as written, because they are the key `photoUrl` is aimed by. No re-join corrects those 146 — opening the screen does.

**Through `cli/resolve.py:box_views`, which is forced rather than preferred:** `capture_server` imports `pipeline_routes`, so reaching `_Places` is the cycle `PipelineRefusal` exists to avoid. Not a second renderer — it is the walk the paragraph above says T7 already holds against `_Places`.

**`place_text` rather than `Position.label`, which fixed a pooled bug on the way past.** `pokemon_code` is `located: False` **and** `catalogued: True`, so its cards do reach a join — and were landing here wearing the one string D24 says may never be printed for them. Its store key also keeps two copies of one SKU from drawing the identical caption in a strip built for stepping between them (D68).

**A box the walk will not answer for gets `null`, never an index-space label** — the store-wide degrade, or a box deleted out from under the run. A bare `BoxView()` would render both in the numbering this entry replaced, beside captions drawn in the other one. The screen shows `no label · <box>/<index>`, which is `BoxBrowse`'s fallback rather than a new vocabulary.

**Two things here are deliberately NOT fixed.** The stored `box`/`index` KEYS go stale too under a mid-box delete (D36); `cli/resolve.py:paperwork_for` realigns them by hashing photographs for the order path, which is too much for a route a screen opens, and it is benign here only because `photoUrl` addresses by slot as well, so caption and picture now agree. And `GET .../file?name=pricing.json` still hands the raw file: a download is the artifact, not a rendering of it.

### What is deliberately not changed

- **`next_index`, `box_fill`, `allocate_capture` and the store schema.** No migration. D10's permanent gap survives intact in the one place it was ever load-bearing — the allocator — which is why T7's two hardest cases, `check_allocator`'s and `check_mark_sold`'s, are untouched.
- **`renumber_blocked`.** Its sold/retired clause's stated reason weakens — the box already closes up over a departure, so there is no gap left to close — but relaxing a refusal is its own decision, and this one would let the mid-box delete shift indices across records that are history and commitments. The refusal stands; the copy on `BoxBrowse` that recited the old reason is corrected, because a refusal explaining itself with something nobody can check any more teaches an operator to read past it.
- **D52, `photoUrl` and `?card=`.** No index moves, so there is no fourth occupant-changing operation.
- **D30's `neighbors`.** Kept, and still worth having for confirming a slot. `section_gaps` is structurally zero for a consolidated box and `placeSentence` already omits the phrase at zero.

### What it costs

**A corrupt record now blanks labels rather than only the decoration, store-wide.** T7 asserted the opposite until today — that one bad record does not take the route down, and every other row keeps its label — on the ground that a label needs only this record's own two integers and the box's layout. That ground is exactly what this removed. A record nobody can place might be in this box and might be on hand, so the count is unknown; answering the index-space label instead would put a second numbering system on the screen with nothing saying which it is, and a person sent to `Card 40` in a box that has sold three would open the wrong slot and see nothing wrong.

**Narrowing the blast radius per box is the fix to reach for if that bites**, and it is not taken here because it would be an untested branch added to make a case go green: a record whose INDEX will not read could be attributed to its box and poison only that one, where a record whose BOX will not read could be in any of them.

**What would reopen this: a box whose slots are fixed.** Everything above rests on the physical fact that a card pulled out of a stack lets the cards behind it slide forward — the same premise D10 ruling 1 already leans on for the mid-box delete. A binder, a sleeved page or any storage where a slot stays empty is a box this numbering describes wrongly, and the honest answer then is per-box rather than global: the flag would sit on `Box` beside `sections`, and the seal gate the owner dropped is the cheapest version of it.

---


## D59 — The live cap is a per-SKU quantity, and a count of one run's positions was answering for it

**The live cap is measured against one quantity — what TCGplayer is holding for this SKU — rather than against a count of the positions one run happens to see.** Built 2026-08-30, from the owner asking what `reconcile` is actually for. They do not run it, and said so: they want the inventory part, not sending a spreadsheet back to the app. That is a legitimate workflow — `emit`, import the CSV, move Staged to Live, mark cards sold — and this entry is what it costs, which turned out to be four defects rather than the tidiness problem it looked like.

### The expression, wrong three ways at once

`pipeline/join.py` read:

    room = self.live_cap - self.live_before - len(self.committed_positions)

`live_before` is the export's `Total Quantity` — **global**, authoritative, D8 and D11. `len(committed_positions)` is **run-scoped**: whatever the box in front of this run happens to hold, derived from the store's per-SKU `pushed + staged` by `cli/resolve.py:_committed_keys`, plus every sold or retired copy in the run. A global cap was being measured against a local count.

- **A SKU split across two boxes had its cap enforced once per box.** Box 1 emits four copies; a run over box 3 cannot see them, reads zero committed, and offers two more — **six rows against a cap of four**, in a file `emit` then tells the operator to import. This is an OVER-SEND, which is Gate B's double-staging defect. `harness/tests/t3_join_coverage.py` holds it as a case and observed the old code offering two. **A randomized sweep was run while this was being designed and its figures are deliberately NOT published**: the instrument was a scratch script that is not in the tree, and a number nobody can re-derive is not evidence.
- **A departed copy occupied room under the cap forever.** `cli/resolve.py` commits every `TERMINAL_STATES` card, and `room` subtracted it a SECOND time — a SOLD copy TCGplayer had already decremented and `live_before` had already counted, and a RETIRED one whose row is still out there and belongs inside the ceiling rather than in a term of its own. It fires with **no listing record at all**: five copies, four retired, never listed, offers nothing. That card is permanently unlistable.
- **`pushed` has no drawdown, so once an import landed the same copies were subtracted twice.** `cli/cmd_reconcile.py` is the only thing that clears it. Measured on the owner's store: **167 copies across 72 SKUs at `pushed`, with `staged` and `live` both zero.**
- **And after a `reconcile`, every SKU with fewer copies than the cap was re-offered.** `_committed_keys` deliberately excluded `live`, so once `pushed` and `staged` reached zero nothing marked an already-live copy as held: one copy, live, `room = 4 - 1 - 0 = 3`, and it went back into the import file. Played forward on the real store one reconcile away — every pushed SKU's copies moved to `staged`, then a join against an export reporting them live — **78 duplicate rows across 61 SKUs, and 0 after this change.** Re-derived directly from `inventory.json`, so anyone can recompute it.

### One number with two consumers

`cli/resolve.py:_copies_out`:

    min(live + pushed + staged, max(live, copies not sold))

*TCGplayer holds at most everything we have claimed, and at most the copies carrying this SKU that have not sold — but never fewer than the export reports live.* `_committed_keys` spends it on positions so a run knows which of its copies not to re-send, and `add_to_quantity` subtracts it from the cap. They were two different numbers before, and that is the whole defect.

**The floor is the export and cannot be argued below.** D8 and D11 put the authority in `Total Quantity`, so the answer is never less than it. **A stale or under-reporting export is therefore harmless WHILE THE PIPELINE'S OWN CLAIM IS STILL STANDING** — `live + pushed + staged` keeps the cap shut even when the export reads zero.

**And after a `reconcile` nothing is standing, which is a hazard this entry does not close.** That corrects a sentence first published as an unqualified guarantee. Once `pushed` and `staged` are both zero, `Listing.live` is the only record left that TCGplayer holds anything, and `_copies_out` does not read it — so a later join whose export under-reports computes `room = cap - 0` and sends the SKU again. **Reading `Listing.live` as a second floor was built and reverted**: `cli/cmd_join.py` sets that field from whatever export it was last handed, so a stale-HIGH stored value would outrank a fresh-LOW export and the SKU would never refill after a sale — T7's own stale-export case went red on it. The two hazards are mirror images and nothing in the data says which reading is newer, so the tie goes to D8 and D11. Pre-existing, unreachable for an operator who never reconciles, and named here rather than claimed away.

**Amended 2026-09-02: the hazard above is closed, by TIME rather than by trusting either side.** `Listing.live_as_of` records when the store's `live` was READ — the export file's mtime for `join` and `reconcile --live`, `now()` for a sale's ±1 and a D34 release — and `Listing.live_reading` is the one rule: the newer reading wins, an equal-second reading is the store's, and a record with no stamp on either side is the export's, as before. `cli/resolve.py:_copies_out` reads it, so the floor under the cap is the NEWEST reading and `SkuMatch.copies_out` no longer `max`es the row's own column back over it; `Listing.observe_live` writes it, so `cli/cmd_join.py` adopts an export's figure only where the file is newer, and the join report names each SKU it kept with both readings. The mirror this entry recorded — a stale-HIGH store outranking a fresh-LOW export — cannot return, because an older store reading loses. D87's amendment of the same day carries the measurement.

**The ceiling was the shelf and is now the sales, because D7's amendment moved the stamp.** It was `max(live, copies not sold)` — we cannot have SENT more copies than we own and have not sold — which held only while `emit` stamped a SKU onto exactly the copies it wrote into a file. D7's 2026-08-30 amendment stamps `uncommitted_positions` instead, correctly, so a stamp means MATCHED rather than SENT and the shelf count silently stopped binding. Measured on the branch before it was fixed: seven copies with four pushed and one sold went from `room = 1` to `room = 0`, and the correction this entry exists for disappeared without a single test going red until the rebase. **The ceiling is `max(live, pushed + staged - sold)`**, aged by the one event that proves a sent copy has left TCGplayer — a copy cannot sell without having been listed — and the sale count survives the stamp move because an unsent backstock copy is on both sides of the subtraction and cancels.

**And it only ages a claim the export corroborates.** With `Total Quantity` at zero nothing of ours was ever live, so the copies are sitting in Staged and a card marked sold against that state did not leave TCGplayer's hands; ageing regardless would double-count every sale the export has already decremented. That guard is load-bearing rather than defensive — dropping it takes `check_listing_commands`' re-emit idempotence case red, which is main's own test.

**The ceiling is what corrects a stuck `pushed` without a second CSV.** `Listing.held` is a claim this Mac made when it wrote a file. It cannot be true that TCGplayer holds more copies than we sent and have not sold, so `store/master.py:Inventory.copies_not_sold` says so. **No write, no inference about what landed, and no Export From Staged.** `pushed` is never cleared and no refusal changes: a box held open by a listing stays held, `renumber_blocked` stands, and D34's release is still the only way to give a commitment up.

**A retired copy still counts as sent, and that is the opposite of `copies_on_hand`.** A sale is proof a copy reached TCGplayer and left it. A retirement (D26) is the other door: the card left the BOX and TCGplayer was never told, so its row is still out there (which is the whole argument for `copies_not_sold` filtering `SOLD` alone), and counting it as gone would free a slot under the cap that is not free.

**What was refused, and it was this session's own first proposal: clearing `pushed` whenever the export reports the SKU live.** It is the obvious fix and it over-sends. `pushed = 4, live = 2` is produced *both* by four went live and two sold *and* by two landed and two are still sitting in Staged, and those want opposite answers — the second is a partial import, and clearing the claim re-offers two copies TCGplayer is already holding. `harness/tests/t7_store_and_seams.py` keeps that as a negative case, green in both builds, for exactly that reason. Two rise-based variants were also tried and under-correct: the drawdown at `cli/cmd_join.py` runs inside the write block, **after** the matches are computed, so it cannot affect the join it runs in.

**`committed_positions` keeps the job it is good at.** It still keeps a copy out of the sellable set, which `uncommitted_positions` reads it for, and D54's delta guarantee is strengthened rather than weakened — no committed copy becomes uncommitted. What it lost is answering for the cap, which is a quantity.

**The placement is inside the existing snapshot and before the write block, and both halves matter.** Before the write, so it fixes the join it runs in; `cli/cmd_emit.py` re-derives through the same `resolve.load`, so join and emit cannot disagree about the committed set, which is D3's rule for `--bypass` one register down. And entirely inside the one snapshot, because a placement that zeroed `pushed` between two write blocks would open a window in which `server/capture_server.py:_stages_held` is empty — and that is the only thing arming `box_not_empty_of_commitments`, `renumber_blocked` and D28's undo refusal. A join that died there would silently disarm three guards on destructive operations.

**Two T3 assertions go red and are rewritten, named here rather than changed quietly.** `t3` asserted that `live` COMMITS NOTHING, and `backstock == 5`. That first sentence is the only place the repo had written the rule down, and this entry is what makes it false: its stated reason — counting the stored live number here would subtract the same copies twice — is still honored, because `live` is now counted **exactly once**, inside `_copies_out`, and `add_to_quantity` no longer subtracts `live_before` separately. `backstock` goes 5 to 2, which is the same double-count read from the other end: six copies with three live and one added leaves two unlisted, and the old five counted the three live copies as backstock as well. **The assertion carrying the real guarantee — `add_to_quantity == 1` — stays green and unchanged.**

**And `at_cap` stopped printing a false sentence.** It said *already at the live cap* for every zero, and under an operator who does not reconcile that is almost never the reason: `live_before` reads 0 on all 167 pushed copies, so the run report and `#/pricing` both told the owner TCGplayer already holds nothing. `SkuMatch.nothing_to_add` names the actual reason per SKU. A card that stops appearing in import files is the silent drop `CLAUDE.md` forbids, and a count under a false sentence is worse than no count.

**What it gives up:**

- **A hand-listed copy is still double-counted.** The export reports it live and no stamped card backs it, so the pipeline adds another. Unchanged from before this entry and inherent: nothing records which physical card backs a listing the pipeline did not make.
- **A review answer stamps a SKU without sending anything, and that stopped mattering when the ceiling moved.** While the bound was the shelf count it over-stated by one per stamp, which this entry first published as one card in 715 and which was wrong by two orders of magnitude — **104 of the 213 stamped cards** got their SKU from an `answered` event rather than from a push. Against a SALES count it cancels: an answer-stamped copy is in `positions_for_sku` and in `copies_not_sold`, on both sides of one subtraction.
- **A retired copy whose row is in an unimported CSV** is shared with the code this replaces. `retire` does not ask whether the SKU has an outstanding push.
- **`backstock` changes meaning**, and it is a correction rather than a side effect: it stops counting a listed copy as backstock. Rendered in `pricing.json` and read by no component.

**What is published here is what can be re-derived from the repository and the store**: the reconcile-forward projection (78 rows to 0), the 167 stuck copies, the one over-stated SKU, and the T3 and T7 cases, each observed failing against the old expressions before it was kept.

**It is invariant under the re-emit that `d3c5101` left owed**, which is the one thing worth checking before that backfill runs. That commit widened the identity stamp and the orders plan's Phase 0 calls for re-emitting `runs/2026-08-30-box3-01` to backfill it, which stamps copies that were never sent. The sales count cannot move: a newly stamped UNSOLD copy adds one to `positions_for_sku` and one to `copies_not_sold` and cancels, and a SOLD copy can never be newly stamped at all, because `emit` walks `uncommitted_positions` and `cli/resolve.py` commits every terminal card — the same guard `d3c5101` cites for not using `match.positions`. Measured: one sold card in the store carries no SKU, and no re-emit can reach it.

**What would reopen this is narrower than it looked, and the orders plan is why.** The reopener named here was a staged quantity the pipeline could read — D34's too. That plan probed every candidate and reports that **no third party can supply one**: `Total Quantity` and `Add to Quantity` are the owner's own listing state, and no mirror, API or export outside TCGplayer's own knows how many copies you have live. So this is not a stopgap with a near expiry; it is the answer until TCGplayer itself offers a staged export the pipeline can read, and that API is closed to new developers.

**What is left is a marker that a copy actually reached an import file.** One field on `Card`, written by `cmd_emit`'s push loop beside the `sku` stamp, would make the bound exact rather than inferred. It is worth less now than when this entry was first written — the sales count is exact wherever the export corroborates a live copy — so it is recorded as available rather than owed.

---
## D60 — The @-loaded docs are dense American technical English, and an entry cites rather than restates

**The three referenced docs are read on demand rather than loaded in full, and their prose is dense American technical English.** Built 2026-08-30, on the owner's instruction to rewrite the prose denser; amended the same day when the measurement showed where the cost actually was.

`CLAUDE.md` `@`-references `docs/DECISIONS.md`, `docs/GATES.md` and `docs/DESIGN.md`, so all four enter context in every checkout, on every turn, before a word of work. Measured the day this landed: **635,411 bytes, roughly 165,000 tokens.**

**The `@`-references are gone, and that is the amendment.** They stayed at first, on the owner's call and against the alternative of an index. What changed is the measurement: rewriting twenty entries moved the four docs 635,411 -> 627,725 bytes, about 2,000 tokens, because these files are ~85% identifiers, paths, measurements and dates and only ~15% rhetorical framing. Dropping the prefix moves the same figure to **~7,700 tokens**, and the two are not close enough to argue about.

**What replaces the load, because a session must not fly blind.** `scripts/decision-context.py` already names the governing decisions before any edit under the mapped directories, and D60's own reflow is what made it see every bold in the file. That covers the edit path. The conversational path — an architecture question with no file open — is covered by the index in `CLAUDE.md`: 60 lines, 3,929 bytes, one line per entry.

**The index is a table of contents and never a substitute for the entry.** `CLAUDE.md` still says to read the entry itself before proposing an architecture change, and that instruction now costs a `Read` where it used to cost nothing. That is the trade, stated plainly: the file is one tool call away rather than already present.

**`decision index` is a blocking audit row, because an index that has drifted is worse than none.** It is believed — D17's argument for auditing `docs/map.py` exactly as hard as it is trusted. It compares ids, titles and order against the headings, which are the source. Mutation-tested three ways: a drifted title, a dropped entry, and a new heading nobody indexed.

**It is not a generator and does not open D18's seam list.** The row computes what the index should say and compares; it never writes. That is D18's own write-time versus check-time split with only the check half built, and the seam list stays empty.

**Cite-don't-restate loses its premise and is narrowed rather than kept.** That rule rested on the cited entry being already in context, which is now false — a reader who follows a citation pays a `Read`. In practice little moves, because the pass that landed was overwhelmingly register rather than deletion: no entry had its argument cut in favour of a pointer. What the rule becomes is the weaker and more honest form — **do not re-derive a cited entry's reasoning, but do say how it bears here**, which is the half that was doing the work anyway. An entry must still stand up read alone.

### The rule

- **An entry opens with a bold sentence stating its ruling.** One line, over twelve characters, ending in a period.
- **American standard technical English.** Declarative. No rhetorical framing, no declamatory capitals, no chains of em-dash asides.
- **Structure carries what signposting used to.** Headings, tables and lists.
- **The owner is quoted as evidence, never as decoration.**
- **Cite, do not restate.**

### Why the opening sentence is a rule and not a preference

`scripts/decision-context.py` builds each entry's summary from its bold runs, ranking sentences ahead of labels and taking the first three. Measured before this landed: **36 of 59 entries led with a ruling, 16 led with a cross-reference or an amendment note, and 7 gave the hook nothing but their title** — D1, D4, D5, D6, D8, D11 and D14.

**That hook reads per line, so a bold run split across a wrap is invisible to it.** These documents wrap at 96 columns, and **270 bold runs — 20% of all 1,318 — were lost that way**, silently, with `make docs-audit` green throughout. Short single-line bold sentences are what fix it.

### Cite, do not restate

**A short citation does real work in one clause and is kept.** *D10 makes their gaps permanent* and *D18's rule: it writes* are the form.

**What goes is the paragraph that re-argues an entry it cites.** Measured at **94 paragraphs over 600 bytes, 77,811 bytes**, across 433 cross-references. Keep how a cited rule bears on this entry; cut the re-derivation of why that rule exists.

**Two limits on cutting one.** A removed citation must leave at least one `D<n>` token wherever `docs/map.py` names the entry in `governed_by`, and must not remove the last mention the audit resolves.

### The structural invariants

**Breaking the hook is silent and breaking the audit is loud, so the silent half is the one that needs a guard.** `scripts/prose-guard.py` is that guard, wired into `scripts/docs-audit.py` as the `decision structure` row.

Frozen because a parser reads them: the `## D<n> — <title>` heading with its dash separator; `docs/GATES.md`'s seven pass-criteria sentences, word for word; its `### Tn` headings, its `Gate X … PASSED` heading lines and every line there beginning with a digit and a period; `docs/DESIGN.md`'s `## Tokens` heading with the first fenced block under it, and its two parenthesized reason-code lists.

**Three phrasings fail a commit and are easy to write by accident.** A sentence naming an audit row by its position rather than its label. An unbalanced fence, which reclassifies every later prose line as code. And an ordinary English phrase beginning *make* placed inside backticks, which reads as a Makefile target.

### Evidence is never reworded

**`docs/GATES.md`'s gate sections are exempt from this entry.** That file rules that its numbers are evidence about a run on a date and are never rewritten, and this rewrite does not touch Gate A, Gate B, Box 2 or Gate C.

### The budget

**A rewrite alone does not hold, which is why the size of a new entry is reported.** Growth over the two days before this landed was **+45,580 and +44,460 tokens**, and **80% of it was new entries** — 21 of them, averaging 11.6KB. A 49% cut is spent in under two days at that rate.

`entry budget` is **advisory**, printing and allowing. A long entry is a judgement call rather than something provably wrong, which is D16's test for what may block; and a blocking row here would teach `--no-verify`, which takes the three opsec rules with it.

### What this is not

**It is editing for concision, not generation.** D18's seam list stays empty and this does not open it. Nothing here is derived from a constant, and no argument is computed.

**It is not license to cut reasoning.** D16 forbids editing a document to satisfy a gate, and the budget row is advisory so that it can never become one.

**What would reopen this: a session that reasons from the index alone.** The index names 60 entries and argues none of them. If decisions start being cited from their titles — or worse, re-litigated because nobody opened the entry — the honest answer is not a longer index but a louder instruction, and `CLAUDE.md` is where it would go.

---

## D61 — The shipping lane is three lanes, and the third answer is "I cannot tell"

**Built 2026-08-30.** `pipeline/shipping.py` reads the TCGplayer Export Shipping CSV and routes one order into one lane; `pipeline/pirateship.py` writes the Pirate Ship import spreadsheet. Every number below is measured against `fixtures/orders-shipping.csv`, 331 real orders.

**The number is the third lane, not the $50 line.** The obvious build is a comparison — under fifty an envelope, over fifty tracking — and it is wrong about two real orders at once:

    < $50, all cards           tcgtracking IMb envelope    (not this entry's to build)
    < $50, contains non-card   Pirate Ship parcel
    >= $50                     Pirate Ship parcel

A **playmat cannot go in an envelope whatever it cost**, and a **$600 single may not go untracked whatever it weighs** — TCGplayer mandates tracking above $49.99. Two independent facts about one order, so a rule reading only the money puts a $12 sealed booster box in a stamped mailer and a rule reading only the contents ships the single. Neither signal subsumes the other.

### The two signals are not the same strength of claim, and the order they are asked in is the whole design

**`Value Of Products` is a fact.** Present on all 331 rows, needs no weight, and $50 is a threshold TCGplayer publishes rather than one this project fitted.

**`Product Weight / Item Count` is a proxy, and it abstains.** It is a summed per-product **catalog constant**, so the ratio proxies *does this order contain a non-single*; the derivation, the five exact values and the empty band are `docs/specs/shipping-export.md`'s and are not restated here. Two numbers cross the seam because the router compares against them: the cut is **0.30**, the geometric midpoint of an empty band 18.4x wide, and the singles constant is **0.07**. Derived from where a real distribution is empty rather than picked, which is D19's rule. Missing on **97 of 331 rows**.

**So the fact is asked before the proxy, and that is worth 58 orders.** Measured: **58 of the 97 weightless orders are at or over $50** and are answered with certainty by a rule that never needed a weight. **Abstention falls from 97 orders (29%) to 39 (11.8%).**

**It also answers the case that spec names as its own worst** — *"it abstains on 29% of orders, and one of them is a $1750 order."* That order is `A2FFC195-0000F4-006AC`, one item, no weight, $1750.00, and this router sends it to a tracked parcel **without consulting the proxy at all**. T7 asserts it by name, because a router that abstained first would still produce three lanes, still count correctly on every weight-bearing row, and still look right.

**The proxy says "heavier than cards alone" and may never say "contains a playmat".** Even at 18x that is an inference. `non_card_signal` produces the same lane the value rule does, so nothing downstream needs the guess sharper than it is.

### Abstention is a third answer, never a default to a lane

`LANE_UNJUDGED` is returned, named and counted. Defaulting it to the envelope ships a playmat in a stamped mailer; defaulting it to the parcel spends postage nobody asked for. **Both are decisions this module is not entitled to make** — the operator is. `parcel_lane` hands the emitter the 126 the router placed there and nothing else.

**Five reasons, because two lanes are reached on different grounds and three abstentions have different remedies.** `Routing.certain` is the split that matters — `value_at_threshold` reads a published price against a published threshold, everything else is the inference — and a screen that cannot tell them apart cannot show which answers are worth checking.

**Two of the three abstentions are latent, and saying so is the point of counting them.** Both report zero over the fixture, and neither is speculative machinery: each is one comparison standing between a silent wrong answer and a visible refusal.

- **`sub_single_weight` is the spec's own named false-negative, turned into an abstention.** `docs/specs/shipping-export.md` records the mechanism and has no row for it: one card plus one weightless non-card reads 0.035 oz/item, *below* the singles constant, so it reads as safer than pure singles. No summed catalog constant can come out below 0.07, so a ratio that does means a product carries less than a card's weight — the weightless non-card itself. Compared only against the 0.30 cut it reads `cards_only`: a playmat in a stamped envelope, silently. The model does not apply, so the router has nothing to say.

- **`no_value_data` was a comment before it was a line of code, and T7 caught the difference.** `route` carried a comment claiming a missing `Value Of Products` landed in the unjudged lane. It did not: a valueless order of pure singles fell past the threshold check, past the proxy, and out as `cards_only` — **a $600 single going out untracked**, from a router whose comment said otherwise. D41's failure (a premise deleted, the conclusion left standing), caught inside the session that wrote it by a test written before the code was believed. **The proxy may not rescue it**, which is why the guard sits above the ratio: a cards-only ratio is the shape an expensive single takes.

### Exact rational arithmetic, never floats

`docs/specs/shipping-export.md` records a float pass **reporting a phantom sub-0.07 row** on a distribution whose true minimum is exactly 0.07 — the one band this router treats as impossible, so **a float manufactures the outcome the bullet above exists to refuse**. Not decoration: T7 run with `Fraction(float(weight))` substituted moves the **lane counts themselves**. `Fraction` and not `Decimal`, because a ratio of two decimals is not a decimal — 45.14/20 terminates, 115/86 does not, and that row is real.

### The emitter: a spreadsheet, because there is no API

**Pirate Ship has no API**, and this is not a gap to work around. Their three first-class entry points are a typed address, a marketplace connection and a **spreadsheet import**; the third is the only one this project can drive, and it is supported rather than improvised.

**`Name` is pre-joined from `FirstName` + `LastName`.** Their auto-mapper is good and it is a guess made on the far side of a seam no committed fixture can test. We own the columns, so it need not work out that two of ours make one of theirs — a recipient addressed as a first name alone is a package at the right street with the wrong person on it, and the failure is invisible from this end.

**`Order ID` is what closes the loop.** `Tracking #` and `Carrier` are empty on **all 331 rows** of the export, structurally rather than incidentally, so carrying the TCGplayer order number across is what lets the tracking number Pirate Ship mints be matched back.

**The rubber stamp makes the label the pick instruction.** Pirate Ship prints three in the label corners, so `Box 3 · Card 31` is read off the thing already in the picker's hand rather than off a second screen. **No label is composed here**: `pipeline/join.py:Position` is the only label formula in this repo and D58 makes drawing one need the box's whole occupancy, so a second formula here is the second-renderer failure already recorded three times. A stamp is an opaque string written out unchanged.

**No length is enforced on a stamp, because nobody has measured one** — truncating at an invented number cuts the end off a pick instruction, and a wrong shelf reads as a right one. Too many stamps refuses, because *that* is knowable from the format.

### Three things the emitter may never do, and all three are D49 in another lane

D49 states it as *"nothing here is ever defaulted on your behalf — that is the entire point"*.

- **It never selects insurance.** An insurance-shaped column **raises** rather than being dropped, matched folded and stripped so a differently-spelled header cannot slip past. Dropping it silently is an operator who believes they asked for insurance and did not; it is a per-order judgement made inside Pirate Ship, looking at the card.

**The named list is a deny list over a set already closed by `COLUMNS`, and what it adds is the reason.** A refusal reading *"not a Pirate Ship column"* invites the fix of adding it. One naming this entry does not.

- **It never buys a label.** No API exists to buy one with, and it would be spending.

- **It never derives a weight, which is the one most likely to be "fixed" later.** The obvious candidate is `Product Weight`, and it is wrong **in the expensive direction**: the catalog constant counts the cardboard and not the mailer, the toploader or the tape, so it is a **lower bound**. Writing it buys postage for less than the package weighs — returned or postage due, at the far end, weeks later. `Package Weight` is whatever the caller measured and blank until they have; Pirate Ship's import sets one weight across every row after the fact, which is where a number off a scale belongs.

T7 asserts the blank **on an order routed by its weight**, so the temptation is strongest where the assertion stands. The first draft took the first order in the lane and passed vacuously: 58 of the 126 carry no weight at all, so it asserted that a blank column stayed blank.

### Buyer PII passes through and is not persisted

Names and addresses enter as arguments and leave as the bytes the caller asked for. Neither module reaches `store/` and neither caches, and `render` returns **bytes rather than a path**, so a buyer's name need never touch a disk. `write_csv` is the one function that writes, and only where it is told.

### The one-way edge, and why this is two modules

`shipping.py` imports `pirateship.py` and never the reverse, so the Pirate Ship format knows nothing about TCGplayer and can be fed by the Bridge untouched. `tcgcsv.py` is the precedent: a foreign format gets its own module.

### This is a pre-line-data stopgap, and it is to be RETIRED rather than tuned

**The export carries no line items at all** — no SKUs, no product names, only `Item Count`, confirmed against a real export. That is what makes a weight ratio the best signal available rather than a proper answer. `pipeline/orders.py` already answers the same question correctly from declared line kinds (`OrderResolution.ships_in_an_envelope`). The day a feed supplies them, **the cut here is the thing to delete, not the thing to re-fit.**

### IT IS A LIBRARY AND NOT A FEATURE

No route, no client function in `app/src/server.ts`, and no screen reaches either module. By `CLAUDE.md`'s route-is-not-a-feature rule it is **not landed**, and this entry says so rather than letting a green harness read as a shipped lane. The remaining half is the unfinished part of this task, not a follow-up to it. `docs/specs/shipping-export.md` said *"nothing reads this file and nothing reads the fixture"*; that is now false in its second half and true in its first, and the spec is amended to say which.

### What would reopen this

**Line items, which retire the cut.** **A measured stamp length**, which makes the unenforced limit enforceable. **Or Pirate Ship refusing the file** — the one thing no committed fixture can hold, because nobody has fed their importer this CSV. Same standing as T6's synthetic composites, and the reason `Name` is pre-joined.

### On this entry's own number

Taken as D61, free now that the number below it has merged; it was contested by two unmerged branches when this was written, which is the heading collision D16 records, in progress again. **The owner's rule, given when asked: always renumber YOUR OWN branch, never another's.** That is narrower than D16's renumber-by-position rule and does not conflict with it — D16 settles headings that have **already** landed, and this settles who yields **before** they do: the incoming branch, always. The alternative is each session moving whichever entry it finds easiest, which is how a cited id comes to point at a different entry.

---

## D62 — The price history is reachable, and it is drawn beside the hold rather than beside the location

**Built 2026-08-30.** `pipeline/pricehistory.py` landed the day before: 1,128 lines, T7 coverage, a tcgcsv catalog walk, an `infinite-api` reader, and every metric a reading needs. Nothing called it, no route served it, no screen drew it. Its own header said so in the words `CLAUDE.md` requires, and named the remedy as a route, a client function, a control and a decision entry. This is that work.

**A label is not a remedy, which is the finding rather than the feature.** The header, `docs/map.py`'s note and the Someday entry all said RECORDED RATHER THAN BUILT, honestly and in the right words — and the capability was exactly as unreachable as the three routes that produced the route-is-not-a-feature rule in the first place. Those shipped with full T7 coverage and no client function. A module is the same failure one package over, and declaring it does not discharge it.

**It goes on `#/pricing` and not on `#/inventory`'s card panel, which is the owner's ruling and reverses where this was aimed.** The obvious home was D38's market row: that panel already reads a price out of the run's `pricing.json`, and a history is the same fact over time. The owner chose the other screen, and the argument is D49's own — the `bullish` withhold and its `watch_above` threshold are the only things in the product that want a trend, and a hold has been set against the operator's memory of what a card used to cost. `#/inventory` answers where a card is; `#/pricing` is where a price is decided. The fact that was missing belongs against the control that was missing it.

**And it keeps D38's closing line intact, which would have been spent the other way.** That entry ends by refusing to let its market row grow controls, on the grounds that a row which does acquires `#/pricing`'s job. A history control would have been the first of those, and the argument for it — a reading is a read, not a write — is the argument that gets made once per control until the screen has both jobs. The row stays one line of text with nothing to press.

**The read leaves the machine, and every other decision here follows from that.** `server/pipeline_routes.py` promised this process makes no outbound call. D33 broke the money half deliberately and replaced it with named guarantees; this breaks the socket half. The letter survives — no socket to Anthropic, no key read — and the sentence meant *this process talks to nobody*, so leaning on the letter would be the drift D16 exists to catch. What replaces it: it spends nothing, because both hosts are public and there is no account to bill; it writes only its own derived cache; it cannot fire on its own, since no screen polls it; and a host being down is a named refusal rather than a stack trace.

**Measured: 1.31s cold, 0.005s warm, 0.67s for a second card in the same set.** The walk is categories, groups, products, then history twice — five requests cold, none warm, and only the two histories for a card in a set already walked. Those numbers are why the control is a press.

**So the panel is pinned and does not follow focus, which is the one place it departs from the photograph beside it.** That photo panel follows the focused row, correctly, because it reads a local file. The same behavior here would fire one request per arrow key: a walk down a fifty-SKU list is fifty reads at a free public mirror for readings nobody asked for. That is the one way this could become rude, and it is closed structurally rather than by a debounce. `T` re-aims the panel, which is a press and therefore an act.

**The panel prints the SKU it is pinned to**, because the consequence of pinning is that the hands move on and the panel does not. Without it, a reading left open while the operator walks the list reads as describing whatever row is focused now.

**`t` for trend, because `h` is spent on the hold** — which is the control this sits beside and exists to inform, so the obvious letter collides with the thing it is for. This screen has spent `m d l s h n p u`; `t` is free, and is a word the owner would say out loud naming what the panel shows, which is the rule `App.tsx` states for the route chords one register up. The same key closes it, matching `p`, so `Escape` keeps its two jobs in the price field. A `T` button sits beside the `H`, because a binding nothing advertises is one only the person who asked for it will press (D51).

**The average is the anchor and the bound is a sanity check, and on a screen that is a type size.** `pipeline/pricehistory.py` names the failure this could take: reporting the bound as the answer, or drawing the two as a price and an error bar of comparable authority. This entry is that caller, so the rule is drawn rather than repeated — the average is the only figure at 26px, the bound is one muted 11px line beneath it carrying its own width, and the ratio between them is the property to preserve if the panel is re-laid-out. It cannot be tightened: the endpoint gives a low and a high per bucket rather than fills, so a true VWAP is bounded and not computable. Measured on Moonfall, $12.54..$20.35 around $16.33 — 48% of the estimate wide, which drawn as a peer would be useless and dishonest at once.

**The two ranges sit side by side and nothing adds them up.** `annual` is not the year before `month`; it is 357 days that include the same recent days at a coarser width. Measured on Vilemaw the day this was built, they point opposite ways — up 71.2% over the month, down 33.9% over the year — and that is the panel working rather than a contradiction to resolve, because a card recovering off a floor is exactly the case a hold is set on. There is no combined figure and no overall row, and one sentence on the panel says the ranges overlap: without it, `+71%` beside `-34%` reads as a broken screen.

**The wider range is also the staler one**, which nobody expects. Weekly buckets are stamped at the start of their week, so `annual` ended 2026-08-24 while `month` ended 2026-08-30 on the same card at the same moment. Each range draws its own span; a shared caption would be wrong for one of them.

**Direction is a sign and a word, never a color.** The palette has no red and no green, `docs/DESIGN.md` locks it, and D50 is the only token ever added against that lock. A rise/fall pair would be a second vocabulary nothing audits, and it would collide with `accent`, which already means unsure and the only action. The panel prints `+71.2%` and the word `rising`, which is also what a reader who cannot tell two hues apart gets.

**The sparkline draws the standing price and says so.** A bucket that sold nothing still carries TCGplayer's own `marketPrice`, so the line is continuous where the sales are not — the honest shape for a trend and the wrong one for a volume reading, which is why volume is a separate row and the two are never combined into one decorated line. A bucket with no price at all breaks the line rather than interpolating across it: Vilemaw's oldest annual bucket is a card that had not been printed yet, and joining through it would draw a year-long slope that never happened.

**D8 is not reopened, and the route is where it could have been quietly.** Nothing in this chain prices anything: no listing price is computed, no `TCG Marketplace Price` is written, `decisions.json` is never touched, and no field on the wire is fed to a rule. The export's own market figure is carried in the payload and drawn at the top of the panel at the metadata register, so the two sit side by side and nothing averages them. The day a listing price may depend on a trend, that is a change to D8 argued on its own terms — one this work makes cheaper to argue rather than one it has already made.

**Four named refusals, because they have four different remedies.** `not_catalogued` — a `misc` card has no `Product Line` to look a category up by, which D22 makes permanent rather than a missing export. `history_unresolved` — no single product matched, and it refuses rather than picking one. `history_unreachable` — a mirror did not answer, and nothing is wrong with the run. `sku_not_in_run` and `pricing_not_written` for the two ways a run cannot supply the row. A panel that said only *failed* would send the operator to the wrong file.

**An empty reading is not a failure and the payload says so.** The endpoint answers HTTP 200 with a null result for a real, catalogued product that has never been seen to sell — measured on two of them — so `never_sold` is a field rather than something the screen infers from an empty list. Read as an error it would report a join defect over a card that is merely illiquid.

**The export row comes off the run, which is why this needed no new storage.** `cli/cmd_join.py:_pricing_table` already writes every matched SKU's export row verbatim under `row`, for D49's reason, and that is exactly the five cells the catalog walk reads. The route re-parses no export, adds no field to any schema, and has one source for what a card is: the run that priced it.

**The cache is the first write that module's header warned about.** It said the first caller would have to think about the `.gitignore` line, with D47's rule attached. `/.cache` is that line — anchored to the repo root so it cannot silently swallow `harness/.cache`, which has its own line and its own reason, and bare so it matches a file, a directory or a symlink. Verified all three ways. It hangs off `files.home()` and is therefore per checkout (D43), so a worktree warms its own rather than writing into the main tree's.

**What is not built, named rather than left to be discovered.** No history on `#/inventory` — that is the ruling above, not an omission. No `watch_above` alarm: D49's watch fires in `join`'s report and nothing here changes that, though this is the reading that would make one worth having. No cross-run view. No second range pair — `quarter` and `semiannual` are real, and `DEFAULT_RANGES` is two because a daily reading and a yearly one are the two questions a hold actually asks.

**What would reopen this: the panel being opened on every card.** It is a press because a read costs 1.3s and a request at somebody else's mirror, which is right for a reading taken on the cards an operator is undecided about. If it turns out to be opened on all fifty, the honest answer is a batched route — `readings_for_rows` already exists in the module and groups by productId — and a column on the row rather than a panel beside it. The measurement is whether the operator presses `T` more often than they press `H`.
**The pointer aims and the key holds** (amended 2026-08-31, by the owner, whose complaint was the panel "persisting on my screen till i close it" and whose remedy was the gesture whole: "if i then push T i see that row's T, and it holds as my cursor moves as long as i hold T, and then as soon as i release it goes away"). Point at a row, hold `t`, let go and it is gone; the row is LATCHED at the press, because a hand crossing to the panel in the far corner passes over forty other rows. The `T` button's click is the other opening and the only one that stands — `Try again`, a scroll and reading while typing all need that, and none can be done with a key held down. The state is `peek ?? pinned` and never one slot, so a glance cannot re-aim a panel somebody left open on purpose.

**Which answers the paragraph above rather than reopening it.** Pointing asks for nothing, so no movement spends a read and the deliberate act this entry required is still a press. A first draft opened on a 350 ms rest of the pointer and was replaced before it was committed. What it costs is a keyboard-only pin, the trade the complaint asked for. `Pricing.tsx` carries the four guards that keep the letter from anything that types. And `p` now closes a pinned reading, which is the half of the corner's mutual exclusion that was never built.

## D63 — The order ledger is two maps, and the sync writes only one of them

**Built 2026-08-30, as the durable half of the order flow.** `pipeline/orders.py` resolves
an order line to the copies that fill it and stores nothing; this is `inventory/orders.json`
and `store/orders.py`, one record per `{source}:{order_number}`, upserted, read and written
through the existing `Store` session in the shape `store/queues.py` uses.

**The split is the design and not a packaging choice.** The resolver's answer is a set of
positions true of ONE `Inventory` snapshot and of no other — D36, which exists because a run
directory's own slot numbers stopped being the truth the moment a mid-box delete slid every
higher card down one — so it is recomputed on every read. An ORDER is the opposite kind of
fact: it happened outside this machine, it outlives every snapshot, and re-deriving it is
not possible at all. One of those must be stored and the other must never be.

### The file has two top-level maps, and `ingest` can name only one

    orders      what the FEED said.  Replaced wholesale on every sync.
    fulfilment  what WE did.         `ingest` cannot reach it.

**One record holding both is the defect this entry exists to prevent.** Ingest replaces by
key, so a fulfilment count living inside the replaced record is destroyed on the next sync —
and the consequence is not a lost statistic. It is the resolver handing out a copy that is
already in an envelope, and a picker walked to a slot whose card left the building on
Tuesday. **The same physical card sold twice**, discovered by the second buyer.

**A careful merge inside `ingest` WOULD ALSO WORK, AND IS REFUSED.** `Queue.upsert` is
exactly that shape — it preserves `first_seen` and refuses to touch a cleared entry — and it
has held for months, so this is not an argument that merges are unsafe. It is an argument
about which property a later session can check. "Two maps, and this method touches one of
them" is verifiable by reading eleven lines; "this merge preserves everything it should" is
verifiable only by knowing every field that must survive, which is a list that grows. The
merge is one refactor from being wrong and the split is not.

**`first_seen` is the deliberate exception and is marked as one.** It is preserved across an
ingest, by the same mechanism `Queue.upsert` uses, because losing a date is cosmetic and
losing a card is not. Naming the exception is what keeps the rule readable: exactly one
field is carried over, and it is the one whose loss costs nothing.

### Ingest writes no card state and no listing count

**NOT `set_state`, NOT `Listing.bump`, NOT ONE BYTE OF `inventory.json`.** Pressing sync
twice is therefore a no-op **by construction** rather than by a guard somebody has to keep
true: `store/orders.py` holds no `Inventory` and imports nothing that does, so it cannot
reach a card. A ledger that moved a card to `sold` on ingest would re-sell every order in
the file on every sync, and a guard against that is one refactor from being wrong. Not
having the capability is not.

**And an unchanged re-ingest rewrites no bytes.** `changed_at` is stamped only where the
feed's content actually differs — T1's own rule for `harness/results/`, which does not
restamp `generated_at` on a cached re-scoring, for the reason that file gives: a one-line
diff on every run is how a real change stops being visible. There is deliberately no
`last_synced_at`, because when the sync ran is a property of the sync rather than of an
order, and storing it would defeat this paragraph to record something no reader needs.

**T7 asserts that as byte equality of three files, which is D54's LESSON APPLIED.** That
entry's guard read `len(rows) == 0` under the message "the file holds no zero row", and "the
file holds 0 rows" is satisfied **identically** by the emitter correctly omitting a row and
by the emitter overwriting two good rows with a bare header; the destruction lived behind it
for as long as it existed. So a second sync here must leave `orders.json`, `inventory.json`
**and** `history.jsonl` byte-for-byte as they were. A row count would go green on a ledger
that threw its fulfilment away and re-ingested the same order over the top.

### Fulfilment is a count, and the one identity it holds is a `capture_id`

**`LineProgress.fulfilled` is a number and is never a list of positions.** D10 ruling 1 lets
a junk capture be deleted from the middle of a box and slides every higher index down one, so
a position written down today names a different card tomorrow. A count survives that because
it names no slot, and it still tells a filled order from an unfillable one — which is the
only thing anybody asks of it.

**`LineProgress.copies` CARRIES `capture_id`s, THE ONE IDENTITY THIS MODULE HOLDS.**
It is minted once per `POST /capture`, it is unique store-wide
(`master.Inventory.card_by_capture_id` refuses a duplicate rather than picking one), and it
survives a renumber by construction: the shift rewrites `box` and `index` and the record keeps
its id. `server/capture_server.py:_drop_from_stores` exists precisely because the two queues
and the answer cache **are** position-keyed and must be remapped by hand at every delete;
a fourth store in that condition is a fourth thing to remember at three call sites, and this
one declines to be it.

**Measured in T7 rather than argued.** Five cards, two pulled at 3/2 and 3/3, then a real
`POST /inventory/3/1/remove`: both pulled copies slide down one, and
**position 3/3 now holds a card that was never pulled**. A ledger storing `["3/2", "3/3"]` ships
it. The case asserts both halves, because the first alone is satisfied by a ledger that
stores nothing at all.

**WHAT `capture_id` DOES NOT SURVIVE, named rather than left to be found: a re-shoot.**
`do_reshoot` requires the NEW photograph's id and writes it onto the record (D26), so a copy
re-shot after being pulled reads as one this ledger has never seen. It is not reachable
through any sequence that makes sense — a pulled copy is in the post and is not
re-photographed — and it is the honest limit on the paragraph above.

### No order state, and no history line

**Nothing is added to `master.STATES`, AND THE TRAP IS D26's EXACTLY.**
`server/capture_server.py:_state_before_sale` and `_state_before_retirement` scan
`history.jsonl` for the last event whose name is in that tuple, so a new member makes both
reversals restore a card to something that is not a state. That is why `removed` was renamed
`retired` on 2026-08-23, and this module stays on the other side of it by holding no states
at all. T7 ingests orders either side of a real sale and requires the reversal to still read
`identified` back out of the log.

**And it logs nothing to `history.jsonl`.** Two reasons, both load-bearing. A sync appending a
line per order would not be the no-op the section above promises, however small the line is.
And this module changes nothing about a card, so there is nothing for that log to describe —
when the pull route is built, **it** touches a card and **it** logs, through `Inventory._log`,
in the same locked session.

### The refusals, each of which is a different way to ship the wrong card

`record_pull` validates everything and then writes everything, which is D29's rule for the
group answer and for D29's reason: a refusal partway through would leave copies recorded
against a pull the operator was told had failed.

- **`CopyAlreadyPulled`** — this physical card is already recorded against another line. The
  thing this module exists to prevent, said out loud rather than counted twice.
- **`CopyNotIdentifiable`** — a copy carrying no `capture_id`. Refused rather than counted
  blind: without an identity the pull cannot be made idempotent, and a silent double-pull is
  the worst outcome this feature has. Every record on the owner's store carries one, so this
  guards a legacy card rather than a common path.
- **`OverFulfilled`** — more copies than the buyer ordered. Refused rather than clamped;
  you cannot ship the fourth, so there is nothing to be gained by hiding it.
  **`Ledger.over` exists anyway**, because a later ingest can REDUCE a quantity under a pull that was
  legitimate when it was made: refuse to create the state, tolerate and report it where it
  arises.
- **`DuplicateOrderLine`** — one order carrying two lines for one SKU. Fulfilment is keyed by
  SKU because that is the only line identity stable across two ingests — a line's POSITION in
  the list is whatever order the feed serialised it in — so two lines sharing a SKU make "how
  many of this have we pulled" a question with two answers.
  **Summing them was the alternative and is worse**: a merged line loses which one was filled.
- **`UnknownOrder` / `UnknownOrderLine`** — a pull against an order never ingested, or a SKU
  the buyer did not order.
- **`BadOrderKey`** — a source carrying the key separator, or an empty half. The key splits on
  the FIRST colon, so a source containing one makes two different orders share a record; an
  order NUMBER may contain one, and that asymmetry is what the refusal buys.

**The key folds case and strips to compare, and stores verbatim** — D20's rule for a box
name, one register over and for the same reason: `TCGplayer` and `tcgplayer` are one
marketplace to a person, and a normalized value written back is a value the operator cannot
correct.

### What it deliberately does not do

**Nothing clears an order.** No `drop`, no `release`. That is `store/queues.py`'s arrangement
for `store/queues.py`'s reason — the queues only grow, because a card in a queue is at a known
position in a box and is not lost — and a cancellation is not a deletion either: `status`
carries the feed's own word for it, verbatim and unvalidated. Deciding what "open" means from
a marketplace's status string is the guessing `CLAUDE.md` forbids, so `Ledger.unfulfilled`
answers the question this ledger actually owns — which orders still owe copies — out of its
own two halves, in the same sequence `pipeline/orders.py:order_sequence` serves them.

**It imports nothing from `pipeline/`, WHICH IS WHY `OrderLine` IS DECLARED TWICE.** The edge
runs the other way and `docs/map.py` records that `store/` imports nothing from `pipeline/`,
so reusing the resolver's frozen `OrderLine` would be a cycle. They are not redundant: the
same split `QueueEntry` has against `pipeline/join.py`'s carriers, for the same reasons — one
is a mutable dataclass that `asdict` round-trips and `__annotations__` filters, the other is a
frozen domain object whose `__post_init__` coerces the SKU. `kind` is carried verbatim and
validated nowhere here, because `pipeline/orders.py` owns `LINE_KINDS` and a second copy is
two lists nothing reconciles — the drift D16 exists to catch.

**AND `parse` FILTERS ON `__annotations__` AT ALL THREE LEVELS.** `store/master.py` records
what one missing filter costs: a field written but not declared is served, persisted, and
**silently dropped** on the next reload, so it looks live right up until the process restarts.
`OrderLine` and `LineProgress` are nested, so filtering only the record lets exactly that
through one level down.

**No buyer, no address, no email.** The ledger holds a SKU, a quantity and what the feed
called the card. `inventory/` being gitignored whole is a reason to keep bearer instruments
out of a commit (`store/files.py`'s code ledger) and not a license to accumulate somebody's
postal address on this disk.

**It does no i/o and holds no lock.** Like `queues.py` it is a data structure; `session.py`
reads it and writes it back inside the lock it already holds. `files.exclusive` polls at 50ms
and gives up at 30s while the feeder captures a card every 623ms, so a module down here that
fetched an order feed would stall real capture — the fetch belongs to the caller, ABOVE the
lock, and `ingest` takes records already in memory. T7 asserts that as an import check rather
than behaviourally, because a behavioural test would have to hang in order to fail.

### What it costs: a fifth file in a set that is not atomic

**`Store.write()` replaces four JSON files in sequence and the set is not one transaction.**
**This is a fifth, and it widens that window by a fifth.** Said here rather than discovered
later. Each file is atomic alone — `files.write_atomic` stages beside the target and
`os.replace`s — and nothing makes the set atomic, so a kill between two calls leaves the store
internally inconsistent. The exposure is live at Ctrl-C frequency rather than theoretical,
which is why D53's supervisor drains in-flight requests before restarting a child, and it is
why the Someday list refuses to put this store on a NAS.

**The only mitigation is an ORDERING, and it is a preference among losses rather than a fix.**
The ledger is written LAST, so a torn write loses the order feed — which can simply be
ingested again, this entry's whole second section being that re-ingesting is free — rather
than the inventory, which names photographs nothing can regenerate. Closing it properly means
one transaction over all five: a staged directory swapped by a single `os.replace`, or a real
embedded store. Neither has been argued, and this entry is not the place to argue it.

### It is RECORDED, not BUILT

**Nothing calls `store/orders.py`. No route serves it, and no screen draws it.**
`CLAUDE.md`'s rule is that a wrap-up claiming BUILT for something unreachable is
wrong rather than merely incomplete, so this entry does not claim it. What is genuinely built
is a store module and its coverage; what is genuinely done is this decision. The precedent is
`pipeline/pricehistory.py`, which the Someday list records the same way and in the same words,
and `pipeline/orders.py` itself, which is reachable only from `cli/resolve.py`'s imports.

**The unfinished part of this same task, named as such rather than as a follow-up**: a route
that ingests a feed, a client function in `app/src/server.ts`, and a control on a screen. Until
those exist there is no order flow — there is a ledger that would hold one.

**What would reopen this: a feed that reorders or re-keys its lines.** Everything above rests
on the SKU being the stable per-line identity across two ingests, which `DuplicateOrderLine`
enforces at the boundary. A marketplace that issues its own per-line id would be a better key,
and adopting one is a schema change plus a migration for every record already written — worth
taking if a real feed offers it, and not worth inventing before one does.

---

## D64 — The Filtered Export is fetched, and completeness is a delta rather than a claim

**The last manual step in `runs -> join` is gone: the server downloads the export instead of the operator, and one press on `#/runs` fetches and joins.** Built 2026-08-30.

`identify` spawns detached (D33) and the three free steps are re-runnable, so the only thing left between a finished batch and a joined run was opening TCGplayer, pressing Export Filtered CSV, waiting, and uploading the file back. `POST /pipeline/runs/<name>/export` fetches it.

**One fetch answers for whatever product lines the portal's filter is set to, which may be several.** A file answers for the games its own `Product Line` cells claim, and D25 has always allowed two games to share one file.

**This entry said the opposite until the first live fetch, and the correction is the useful part.** It read that all eleven of the owner's historical exports carry a single product line, and concluded that a mixed-game run needs one fetch per game. The premise was true of those eleven files and was never a fact about the portal. Measured on the first authenticated fetch, 2026-08-30: 394 rows over six product lines, and `games_claimed` answered `pokemon`, `pokemon_code`, `riftbound` and `one_piece` from one file.

| product line | rows |
|---|---|
| Pokemon | 203 |
| Riftbound League of Legends Trading Card Game | 145 |
| One Piece Card Game | 42 |
| YuGiOh | 2 |
| Card Sleeves | 1 |
| Playmats | 1 |

**A generalization drawn from stored files rather than from the rule is what failed here.** D25 already decided this and the pipeline already handled it; the limitation existed only in this prose.

### What replaces the promise

**This process now holds a secret and opens a socket, and the sentence that said otherwise is rewritten rather than narrowed.** D33 already broke the money half of `capture_server.py`'s header. What survived was a file-boundary claim beside the import: no key, no socket, no child. `server/tcg_export.py` reads a TCGplayer session cookie from `.env` and opens a socket to `store.tcgplayer.com`.

**Narrowing it to "no socket to Anthropic" was available and is refused.** That is the drift D16 exists to catch.

What holds instead: one host, one method, one route, in one module with one caller, and it cannot cause a charge. `POST /pipeline/identify` is still the only route that can.

### The probe that would make this simpler is still open

**Every seller-admin route answers `302 -> /admin/account/logon` unauthenticated, before any parameter is read.**

| route | unauthenticated |
|---|---|
| `GET /Admin/Pricing/DownloadMyExportCSV` | 302 to logon |
| `GET /admin/pricing/getjsonfilters` | 302 to logon |
| `GET`/`POST /admin/pricing/productsearch` | 302 to logon |

This is cookie-session auth, not the order-management API, which is another host answering `www-authenticate: Bearer`. The two were conflated once while this was scoped and reached the wrong conclusion.

**Amended 2026-08-30: the `Bearer` half is measured false, and the sentence stands because the conflation it warns about was real.** The order host is a cookie session on the same `.tcgplayer.com` ticket this table's host uses; what does not transfer between the two is the body convention, not the auth. D69 has the capture.

**Whether export scope can be set by request is therefore unanswered.** It needs one authenticated probe, which needs the cookie, which only the owner can place. If scope can be set, the better design is to ask for a scoped export rather than inspect a broad one: fetch the sets the run needs with printings and conditions unfiltered, and the file is complete within scope by construction. That is recorded and not built, because a path that has never run must not carry a comment claiming a property nobody measured.

**Its scope source does not exist yet either, which is the second finding.** No identification profile returns a set. Measured across all four runs on disk: `pokemon_card_v1` answers `{name, number, printed_total, finish, confidence}` and `riftbound_card_v1` answers `{name, number, finish, confidence}`. `printed_total` is a denominator. The set is knowable only after a join, from the export's own `Set Name` column, which is circular for deciding what to fetch. `set_hint` is the only pre-join source and covers 676 of 715 cards; box 3 carries none and spans six Riftbound sets.

### Completeness cannot be read off an export

**Three filters narrow a Filtered Export independently, and one leaves no trace in the file.**

| axis | visible in the file |
|---|---|
| printings (All Printings off) | yes |
| condition | yes |
| listings with photos | no — `Photo URL` is empty in all eleven exports, filtered and unfiltered |

**The obvious guard fails because the axes are independent.** Refusing a file with no non-Near-Mint condition row passes an All-Printings-off export, which still carries every condition for the printings it does contain.

**What missing printings cost is a silent mislisting.** D3 rung 2 fires when exactly one condition row exists for a number, so a variant-thinned file manufactures single-row numbers and a reverse holo with no finish claim resolves to the normal row. A missing SKU is loud by comparison: the card queues as `no_catalog_row`.

### The guard

**Completeness against the catalog is unknowable; completeness against this run's own previous export is arithmetic.** Two readings, per game the fetch answers for.

- SKUs the baseline carried and this file does not.
- Numbers that had several finish rows and now have one. Counted over `condition_by_finish`'s own values, and keyed the way the row would be found: by `(Set Name, Number)` where there is a number, by name where there is not.

**One refusal code covers both, because a condition row is a SKU.** A number cannot lose a printing without losing the row that carried it, so a second code could never fire alone.

**`cli/resolve.py:exports_for` does the ruling, so the check is the real rule rather than a second approximation.** It runs over the fetched file plus whichever recorded exports it does not replace, before anything is joined. `games_claimed` is extracted from it for the one thing the route must know first.

**Two acknowledgements, each named for the fact it answers.** `accept_narrower` says the file covers less than the last one and the operator means it. `accept_unverified` says the run has nothing to compare against. Separate fields because one is evidence and the other is its absence.

**The first join of a run costs one acknowledgement and every re-join is autonomous.** `join` is free and routinely pointed at a refreshed export, which is where the fetch does its work and where a baseline exists.

### Both readings were wrong in the first build

**Measuring against the owner's real exports found two defects that a three-row fixture could not.** Both made the check look like it worked: one fired on everything, one on nothing.

**Play conditions are not finishes.** D12 scopes the product to Near Mint and the committed fixtures are Near-Mint-only; a wide export carries eleven to sixteen conditions because it also lists Lightly Played through Damaged. Measured on box 3's export against the wide Riftbound file: all 153 numbers read as thinned and **not one had lost a finish**. The refusal would have fired on an operator doing the right thing, carrying a sentence about mispricing that was false.

**The key carried `Product Name`, which loses real cases.** Finish variants usually share a product name, 143 of sv09's 144 multi-row numbers. Keyed `(set, number)` the wide Riftbound export has **550** numbers stocked in more than one finish; keyed with the name, **522**. Twenty-eight were invisible to the check written to find them.

**The guard does not fire on the owner's own refresh.** Run `2026-08-29-box1-01` holds two real exports taken four minutes apart, 60 rows then 2,008. It allows them. A guard that refused a legitimate widening would be read past rather than read.

### Three defects this branch found in itself

**A one-second filename stamp let a second fetch overwrite the export the run was joined against.** That file is the baseline the guard compares to, so the check then compared a file to itself and passed. The name carries a content digest now, and a refusal deletes only what the request created. T7 found it before the route had run for real.

**The remedy `tcg_session_expired` prints did not work.** It tells the operator to replace the value in `.env`, and `envfile.get` could not see them do it: `load` returns early once loaded, and it will not overwrite a name it set itself. Neither cache had mattered before, because an API key and a mirror path are placed before anything starts. A session expires, and D53's supervisor runs for days without watching `.env`. `envfile.get_live` reads the file fresh; `_from_file` keeps a real environment variable winning.

**The CSRF gate's stated reason was falsified by this branch.** `capture_server.py` justified the origin check with "there are no credentials in this product", which now understates what it guards: a page in another tab could otherwise make this server spend the owner's marketplace session. The conclusion is unchanged and the reason is corrected. T7 asserts the refusal lands before the cookie is read.

### What it costs

**The fetch composes with the recorded exports and `join` does not.** `exports_for` replaces the recorded mapping outright once any `--export` is passed, which the upload path has always done. So on a mixed-game run, fetching one game's file and joining with it alone passes the fetch and refuses at the join, naming the uncovered game. Making a recorded export compose with an explicit `--export` changes that function's contract and has not been argued. It is a narrower case than it looked when this was written: a fetch returns whatever product lines the portal's filter holds, and the measurement above shows that covering every game the run holds in one file is the ordinary state rather than the exception.

**The cookie is a bearer instrument and `.env` is the only place it lives.** Never logged, never in a refusal message, never written into a run directory; T7 asserts the last over every file the run holds. `PKMNSCAN_TCG_EXPORT_URL` refuses to carry it anywhere but https or loopback, because a knob that redirects a session cookie is an exfiltration channel wearing a test seam. One redirect hop is followed, and the cookie is not re-sent across a host change.

**What was fetched is downloadable.** `_artefacts` lists off the run directory, so the operator can open the file this route summarizes rather than trust the summary.

**The WAF does not block an authenticated stdlib client, measured 2026-08-30.** The owner placed a session cookie and the fetch returned 68,363 bytes over 394 rows. This was the one thing the entry recorded as owed, and it is the reason `PKMNSCAN_TCG_USER_AGENT` exists: the earlier unauthenticated measurement said nothing about a request carrying a session, so a block was a plausible outcome the build had to survive. It did not occur. `tcg_blocked` stays, because one measurement on one day is not a guarantee about a rule somebody else maintains.

**What that fetch also showed is that the portal's saved filter decides what arrives.** It returned the owner's current listings — eight conditions including `Unopened` and the Lightly Played family — rather than a catalog export. That is not a defect in the fetch, and the guard is what catches it: against box 3's baseline the same file carries 145 Riftbound rows to that run's 153, so it refuses `export_narrower` and names what went.

**Amended 2026-09-02: the delta guard is retired.** D65 met the condition above the same day and names the scope, so this guard's remedy asked about a Pricing-tab filter the request overrides. A run directory is new per run, so `previous is None` on every first fetch and `export_unverified` fired on every run — a 1.7 MB download unlinked and fetched again on a press; `export_narrower` fired on a legitimate set-scoped fetch after a category-wide one. Both codes, both fields, `_coverage`, `_printings` and `_finish_conditions` are gone; `export_scope_incomplete` is the whole guard; the receipt carries `previous`, the last joined export's file, rows and SKUs per game, and refuses nothing on it. The filename finds identical bytes by digest before it stamps — with the stamp first, every re-fetch added a copy, and `2026-08-31-box3-01` holds two byte-identical 366 KB exports 29 seconds apart.

---

## D65 — The export is asked for, and the box's own claims are the scope

**The export request names what it wants, so completeness stops being an inference.** Built 2026-08-30.

D64 fetched whatever the portal's saved filter last produced and then tried to judge it. This names a category and a set in the request, so the file is complete within that scope by construction.

### D64 shipped against the wrong endpoint

**`/Admin/Pricing/DownloadMyExportCSV` ignores every parameter, measured across eight spellings that returned byte-identical output.** It is a different, unscoped endpoint that serves the saved filter. It entered D64 as a verified fact, it does return a CSV, and that is how it survived.

**What the Export Filtered CSV button sends is `POST /admin/pricing/downloadexportcsv`**, captured off the wire in the owner's browser. The scope travels in the body, which is why every query string was ignored.

### The body was guessed wrong five times

**Captured by intercepting the portal's own form submit rather than inferred from its bundle.** The bundle gives the field names; it does not give the types, and the types are the part that matters.

| field | inferred | actual |
|---|---|---|
| `PricingType` | `1` | `"Pricing"` |
| `CategoryId` | `89` | `"89"` |
| `SetNameIds` for all | `[]` | `["0"]` |
| `PriceToCompare` | `null` | `3` |
| `ExportLowestListingNotMe` | `false` | `true` |

**Every value is a string, and "all of them" is `["0"]` rather than the empty list.** `0` is the "All Set Names" row's own id, so the portal asks for a filter matching everything rather than for no filter.

**Two fields are never negotiable.** `MyInventory: false` makes it the catalog rather than the operator's current listings, which is what a join exists to add to. `PrintingIds: ["0"]` is All Printings, because a number stocked in several finishes must arrive with all of them or D3 rung 2 decides it from whichever survived.

### The guard flips from a delta to a positive check

**D64 compared a fetch against the run's previous export because nothing better was available.** Three filters narrow an export independently and one leaves no trace in it, so completeness could not be read off the contents.

**A scope this process named can be checked against what arrived.** The question becomes "did I get the sets I asked for", which the file answers. `export_scope_incomplete` refuses rather than warns: a set asked for and absent means every card in it queues as `no_catalog_row`, a whole box silently, from a fetch that reported success.

**There never was a delta guard on the upload path, and the fetch path's was retired 2026-09-02** (D64, amended): the positive check is the whole guard.

### The scope is the claims the operator already made

**A card carries its game and, where the operator set one, a set hint.** A box captured as Riftbound/Unleashed already says which category and which set its export needs, so nothing new is asked of them.

**`match_sets` reads a hint against TCGplayer's own set names in three rules** — case-folded equality, then prefix, then the name's leading token before a colon. Measured on the two the store holds: `UNL` resolves to `Unleashed`, and `ME01` resolves to `ME01: Mega Evolution` across 220 Pokemon sets.

**Substring is deliberately not one of the rules.** `Origins` appears inside `Origins: Proving Grounds`, so a substring test makes every hint naming a base set ambiguous with its own sub-sets and resolves nothing.

**An ambiguous hint matches nothing and the fetch widens to the whole category.** Widening is slower and always correct; narrowing onto a set the box is not in is not. Riftbound entire is 10,118 rows against Unleashed's 2,201, and that is the whole price of being wrong in the safe direction.

### One category per fetch

**`CategoryId` is scalar in the portal's own request, so a mixed-game run fetches once per game.** The request takes `game` and refuses `game_required` when a run holds more than one, naming them. The join composes what the fetches leave behind.

### A refusal that blamed the operator's credential

**The portal answers a malformed request with HTTP 200 carrying an HTML page titled `System Error`, and D64 read any HTML as a login page.** Five different bad bodies were each reported as `tcg_session_expired`, which sends the operator to re-copy a cookie that was working. `tcg_request_rejected` now says the session is fine and the defect is here.

### What it costs

**The category ids are registry data that only the portal knows.** `tcgplayer_category_id` sits beside `product_line` in `pipeline/games.py` — Pokemon 3, One Piece 68, Riftbound 89 — because the two are independent identifiers for the same thing and neither derives from the other.

**This module now makes two calls rather than one.** `getjsonfilters?categoryId=N` reads the vocabulary; without a category it returns one "All Set Names" row and nothing else, which is why it takes the argument.

**The hint vocabulary is not TCGplayer's, and a table is the only bridge.** Measured against the live category lists: `UNL`, `ME01`, `SV05` and `SV09` resolve by shape, while `OGN`, `MEG`, `TEF` and `JTG` — the community short codes — resolve to nothing and widen to every set in the category.

**No derivation rule reaches them.** `MEG` is not a prefix, an initialism or a colon-token of `ME01: Mega Evolution`, and `TEF` is none of those for `SV05: Temporal Forces`. So `set_aliases` sits in the registry beside the game's other hand-authored vocabulary, which is D22's rule for exactly this.

**It is deliberately partial and maps a code to another HINT rather than to an id.** There is no machine-readable source for community codes, so it covers what the owner types and grows as they type more; and resolving `MEG` to `ME01` lets the three shape rules do the matching without the table repeating a full set name that TCGplayer may re-word. An absent alias costs a wider export, never a wrong one.

### The whitelist at capture time

**The capture screen offers the real set names, so a new hint is exact by construction.** `GET /tcg/sets` serves the game's vocabulary and the hint field is a `datalist` over it, with the alias codes listed beside the names so the field is searchable by either.

**A datalist rather than a select, because the rig may not be constrained.** It suggests without restricting: free text still works, and an empty list is indistinguishable from the control before this entry.

**Every failure answers 200 with an empty list and a reason.** No cookie, no network, the portal down — the operator keeps typing. D19 measures this screen's cadence in milliseconds and a hint field that would not open because an autocomplete failed is a worse product than one with no autocomplete.

**And the reason is drawn, because degrading to empty is correct and degrading invisibly is not.** The first build carried the reason on the response and threw it away, so an expired session and a game with no sets produced the identical empty list and silence was the only signal. The session case names `.env`, since it is the one the operator can act on. It stays a note: the field takes text exactly as before.

**`#/runs` already said so and the capture screen did not**, which is the asymmetry worth recording. The fetch refuses with `tcg_session_expired` and the screen renders the sentence verbatim with no control, because re-copying a cookie happens outside the app. The capture screen had no equivalent, and the hint field is the surface an operator touches long before they ever press Fetch.

**The load follows the field being OPEN, not the row being tapped**, which was a real defect caught by its own test. `H` opens the field from the key handler and never reaches the row's `onToggle`, so hanging the load there left the list empty for every operator using the keyboard — which on this screen is all of them.

**`match_sets` stays regardless.** 677 of the store's cards already carry free-text hints and those runs must keep joining; an exact hint costs the matcher nothing, because rule one matches and the other two never run.

### The field had rules and drew none of them (amended 2026-08-31)

**A `datalist` offers a vocabulary and says nothing about the string actually typed.** That is the whole of the defect the owner reported: the hint became a whitelist field above, and the control still looked like the free-text box it replaced. `Spiritforge` and `Spiritforged` are indistinguishable at the rig. They part company an hour of captures later at the fetch — one scopes the export to that set, the other resolves to nothing and widens to the category — and the operator learns which they typed from a row count on a different screen.

**So the field says which of the two it is, while it is being typed.** `app/src/setHint.ts` resolves the hint against the vocabulary the field is already offering and answers in five states: `blank`, `unchecked`, `matched` (with the set, and whether the hint IS its name), `ambiguous`, `unmatched`.

**Two registers, because the Box field beside it already has two.** A terse meta pinned to the right of the entry for the state — that field's own `next 60` / `new box` — and a sentence under the field for what the state means. Nothing here is a new shape; it is the screen's existing grammar applied to the one other free-text field on it.

**It judges and never refuses, which is the rule above unamended.** Every string can still be stored, `unmatched` included; the sentence says what will happen to the hint rather than asking for a different one. Accent at text weight, which is `docs/DESIGN.md`'s "the system is unsure" job — never a halt outline, because nothing is halted.

**`unchecked` is a first-class verdict and the reason the feature is safe.** No cookie, no network, the list not yet fetched: the screen says it cannot tell rather than accusing the operator of a typo it has no way to see. The at-rest row is silent in that state too. An empty vocabulary already had to leave the field working; now it also has to leave it quiet.

**Enter completes a hint that resolved but is not the set's name.** An alias, a prefix or a colon-code scopes the export correctly and is still not the string `pipeline/join.py:set_matches` wants at join time — that matcher folds and compares, with no prefix rule to save it. The keystroke that leaves the field is therefore the one that makes the stored hint exact, which is what "exact by construction" above promised and the `datalist` alone never delivered. It completes nothing that did not resolve.

**The copy is asserted against the original, because a verdict gets trusted where silence did not.** `scripts/set-hint-agreement.py` runs `app/src/setHint.ts` under node against `server/tcg_export.py:match_sets` over 22 hints drawn from this entry's own measured vocabulary, and compares the one fact both stake a claim on: did this hint resolve, and to which set. A screen that says MATCHED where the fetch misses is worse than the field was before this section. This is `scripts/port-agreement.py`'s shape one decision over, and it is off the commit path for the same reason: it runs node.

**What the two sides may still differ on is the shape of a MISS, deliberately.** `match_sets` returns one "missed" list; the screen splits it into `ambiguous` and `unmatched`, because "two sets answer to that — `Origins` and `Origins: Proving Grounds`" is an instruction and "no match" is not. The agreement check reduces both to resolved-or-not, which is the claim that has to hold.


### There were two matchers, and a set code resolved to neither (amended 2026-08-31)

**The paragraph above about Enter completing a hint is overtaken, and the sentence that overtook it is the point.** It said an alias or a prefix "is still not the string `pipeline/join.py:set_matches` wants at join time", and that was true: this repo answered *does this hint name this set* in two places, by two different rules. The fetch had a prefix rule and raw case-folding. The join folded `sv09` and `sv9` together and matched either side of a colon. So a hint could scope the export correctly and then fail to narrow the very rows it had fetched, and the verdict this entry added to the capture screen predicted only the first half of that.

**One ladder now, in `pipeline/setnames.py`, read by both.** Whole label, then either colon side, then a guarded prefix, then an abbreviation. `server/tcg_export.py:match_sets` keeps only what is genuinely its own — mapping a resolved name back to the portal's set id, and dropping the `All Set Names` row before resolution rather than after, since dropped after it makes a real set look ambiguous.

**Merging them fixed a defect that was live and had nothing to do with set codes.** `set_matches` is PAIRWISE — one hint against one name — so it cannot see how many sets answered. Four did: `SV` matches `SV: Prismatic Evolutions`, `SV: Paldean Fates`, `SV: Scarlet & Violet 151` and `SV: Shrouded Fable`, and `Catalog.candidates` handed all four sets' rows back as a confident narrowing with no `set_ambiguous` and no review. Resolution is set-wise now and answers `None` on a tie, so that card reaches a human with its photo (D2, D3). `set_matches` survives as the yes/no question T3 asks of one pair, delegating to the shared ladder.

**A set code is derived from the set's own name, not looked up.** The letters of a short hint, in order, anchored on the first, running through the name with any block code taken off the front: `SFD` finds Spiritforged, `OGN` Origins, `VEN` Vendetta, `TEF` Temporal Forces, `JTG` Journey Together. There is no rule that yields the ONE official code — `TEF` is two letters of Temporal plus one of Forces, `SFD` is a squeeze of a single word, `OGN` skips two letters and keeps a third — so every ordered squeeze is accepted and ambiguity throws out the ones answering to more than one set.

**THE RULE NEVER HAS TO KNOW WHICH SQUEEZE IS OFFICIAL, AND THAT IS THE PROPERTY THAT SAVED THIS SECTION FROM ITS AUTHOR.** An earlier draft named `VDT` as Vendetta's code. It is not; `VEN` is, and `VDT` was a session pattern-matching three consonants out of a set name and then citing itself. Because the rule accepts every ordered squeeze, both strings resolve to Vendetta and no code changed — but the entry asserted a fact about the world that nothing had checked, which is precisely what D22 exists to stop, and it did so two paragraphs after arguing that scraping was unnecessary because no source had to be trusted.

**The alternative was scraping a code table, and BOTH halves of the argument against it were wrong.** The claim was that a scrape yields only *code to community name*, and that the second hop — community name to TCGplayer's own label — is published nowhere. It is published: `https://tcgcsv.com/tcgplayer/<category>/groups` serves TCGplayer's own group names, unauthenticated, and this repo already vendors fixtures from that host. Measured against it on 2026-08-31, the derivation covers **6 of 7 Riftbound codes and 13 of 22 Pokémon SV01-onwards codes**. It is a good reduction of the table, not a replacement for it, and the session that argued otherwise had never looked at a full-size vocabulary.

**Three of the four hand-authored alias rows are dead and the fourth is load-bearing** — `TEF`, `JTG` and `OGN` derive; `MEG` does not, because `ME: Mega Evolution Promo`, `ME01: Mega Evolution` and `MEE: Mega Evolution Energies` all answer to it and a tie widens. An earlier draft of this paragraph called all four dead, having measured against an eight-set list assembled by hand; against TCGplayer's real 29 SV/ME sets that is false. The dead rows are kept anyway: D22 makes the table the owner's, and a row costs a dictionary lookup.

**Every miss at full scale is a TIE, and not one code resolved to the wrong set.** Nine Pokémon codes and one Riftbound code need a row, and each is a code answering to two or more sets — `PAL` to Paldea Evolved and Paldean Fates, `MEG` to the three Mega Evolution groups, `SCR` to Stellar Crown and the four `Scarlet & Violet` ones. That is the failure this rule was designed to have: the export widens, which is slower and cannot miss a card.

**Two guards, both measured before either rule was written.** The abbreviation is capped at four characters, because uncapped it silently resolves `Spiritfoged`, `Vendeta` and `Orgins` to their intended sets — which sounds like a feature until you notice almost every string then "names a set" and the typo warning this section added never fires again. And a prefix may not split a number: `unl` is Unleashed and `sv` is every SV set, but `sv1` is not `SV19`, which `harness/tests/t3_join_coverage.py` asserted long before the two matchers met.

**What bounds the damage is the rule's position and the game picker, and the measurement says so — but read what the measurement was over.** The abbreviation is tried last, so it can never take a hint that already resolves. Against the real committed export lists, judged within the game the operator has already chosen, thirteen of thirteen strings resolved to the intended set and none resolved wrongly. **Seven of those thirteen are codes with a source** — typed by the owner, or already hand-authored in `set_aliases`, or carried by store records. **The other six were chosen by the session to exercise the rule's shapes** and are not evidence that anybody types them. The number is a claim about the MATCHER and not about the vocabulary; a claim about the vocabulary needs the owner or the rig, and this entry does not make one. The only way it returns the WRONG set is for the operator's own set to be missing from TCGplayer's list — if their set is there, the code either finds it or ties with another, and a tie widens. An earlier draft of this section quoted a one-in-twelve error rate; that number was measured across games, typing Pokémon codes at a Riftbound vocabulary, which the game picker makes unreachable. It is recorded here because the wrong measurement nearly bought a worse design.

**Measured at full size on 2026-08-31, after this entry twice recorded a number taken off the fixtures.** TCGplayer lists 12 Riftbound groups and 29 Pokémon SV/ME ones. Ties do become commoner with scale, exactly as predicted, and the failure that grows is the rule declining to fire rather than answering wrongly — the wrong-set count at full size is zero. What the fixtures could not have shown is how MUCH commoner: nine of twenty-two Pokémon codes tie, which is what turns the hand-authored table from a legacy into a live requirement.

**One wrong answer does exist, and it is older than the abbreviation rule.** `SP` is Riftbound's Special collection, TCGplayer lists no such set, and `SP` resolves to `Spiritforged` by the PREFIX rule — which has answered that way since `match_sets` shipped. It is left alone: narrowing prefix would take `UNL` and `VEN` with it, and both are real codes for sets TCGplayer does list.
---

## D66 — The order screen comes before the transport, and the shipping lane needs neither

**Recorded 2026-08-30, and nothing here is built.** `docs/specs/order-pipeline.md` is the plan that produced it — steps 8 to 14, order in to tracking back — landed out of a planning session whose findings were living in a chat transcript. This entry settles the ORDER the remaining work is done in, because a five-session sequence had already been written down and two of its dependencies do not exist.

**Three modules have full T7 coverage and no reachability whatsoever**: `pipeline/orders.py`, `pipeline/shipping.py` and `pipeline/pirateship.py`, covered by `check_order_resolver` and `check_shipping_lane`, with no route, no client function in `app/src/server.ts`, no subcommand and no screen. `store/orders.py` is the fourth module of the order flow and is the exception — see below. `make harness` and `make check` are green over every one of them. That is `CLAUDE.md`'s route-is-not-a-feature rule and this repo's own recorded failure, at four modules at once.

### The screen is built before the transport, and the reason is the Done criterion

**A transport-first session cannot state a Done this repo accepts.** The version this reverses read *"an order from the live account lands in `inventory/orders.json`; ingest writes no card state; a replay is a no-op"* — three true and testable sentences, all of them server-side. Every one is satisfied by an ingest route no human can reach, which is the exact shape the paragraph above indicts. It carried a paste door as its first deliverable, and a paste door is a control: it needs a screen, so that session either ships the unreachable half or silently contains the screen session.

**The screen first is a complete product with no network in it.** `resolve_all` returns picks, `pipeline/join.py:Position` labels them, and `store/orders.py` already holds `record_pull`, `forget_pull` and `holder_of` — so a screen fed by pasted JSON pulls a real order end to end. The transport is then a better source behind a control that exists, which is a smaller change than a route looking for a home.

**`store/orders.py` is the half-wired one, and that is what makes this cheap.** `store/session.py` carries `Ledger` in `Snapshot` and writes it last on every store write. The ledger is loaded and persisted already; it has simply never had an order put in it.

### The shipping lane is not downstream of either, and the dependency graph said it was

**`pipeline/shipping.py` reads the Export Shipping CSV, which carries no line items at all.** Its `Shipment` says so in its own docstring, `to_parcel`'s `stamps` argument **defaults to empty** and its docstring states that nothing there knows where a card sits, and `fixtures/orders-shipping.csv` is committed at 331 real orders. So the parcel lane is reachable from an uploaded file with no order feed and no resolver, and the resolver's only contribution is the location in `Rubber Stamp` — optional by construction rather than by omission.

**The limit, stated so this is not read as a license to parallelize.** The engine dependency is zero and the surface dependency is not: if the lane badge and the download draw on the order screen, two branches revise one file, which this repo has already paid for twice. Sequence them, or give the lane its own surface.

### One exclusion is struck, because D64 shipped the thing it excluded

**"Python bearing the session cookie" was ruled out and is now running.** The exclusion's reason — the extension reduces the cookie to a yes-or-no answer and never exposes its value — was an argument about the extension, and it was carried to a conclusion it does not reach: the owner can place the cookie themselves, which is what `server/tcg_export.py` reads out of `.env`. The row stays visible in the spec rather than being deleted, because sound reasoning arriving at a wrong conclusion is worth being able to find again.

**What survives is one probe, not a session.** The admin host answers a cookie-session 302 and `order-management-api` answers a Bearer challenge; two hosts, two schemes, and D64's result does not transfer. That question is answered by one request, and the spec puts it in the free work rather than letting a build be organised around it.

**Amended 2026-08-30 (D69): the probe ran, and answered cookie rather than Bearer.** `order-management-api.tcgplayer.com` authenticates with `credentials: 'include'` and the same `TCGAuthTicket_Production` cookie the admin host uses — one `.tcgplayer.com` session, two hosts — so *two hosts, two schemes* is one scheme, and D64's result DOES transfer as far as auth is concerned. The paragraph is amended rather than removed because its structural claim was right: one request settled it, and organising a build around the answer would have been organising it around a guess. What does not transfer is the body convention — form-urlencoded `model=<json>` there, plain JSON here. The capture, the two calls, the required `sellerKey` and the 403 that reads like an expired session are all in D69.

### The relay, if it is built, is work this repo cannot verify

**There is no extension in this tree.** The requirements set on it — an exact derived origin, an action allowlist inside the extension, its own rate limit, since `onMessage` has none — are changes to a codebase `make check` never sees, `docs/map.py` does not map and the git hooks do not guard, in a project whose verification argument rests on those three. Not a reason to reject it; a reason the session that takes it states the cost up front instead of finding it halfway through.

### What this does not decide

**Not the resolver, the ledger or the lanes** — D63 and D61 settled those and this entry re-opens neither. **Not whether the relay is the right transport**, which the probe decides. **And not the eleven rulings the planning session took**: they are recorded in the spec with their original letters, two of them already overtaken by built code, and this entry deliberately does not restate them.

### What would reopen this

**A screen that turns out to need the feed to be built at all** — the claim here is that pasted JSON is a sufficient input, and it is untested until somebody pastes one. **Or the probe answering Bearer**, which does not change the order but does change what the transport session is. *(It did not: the probe ran 2026-08-30 and answered cookie — see the amendment above and D69.)*

---

## D67 — The number a screen draws is composed once, and the set code D55 strips for the key is stripped for the eye

**Built 2026-08-30, from the owner looking at five copies of Moonfall in box 3 and seeing the `Number` row disagree between them.** Two defects with one repair between them: the collector number is now composed by ONE function per side of the wire, and the glued-on set code D55 removes to find a catalog row is removed to draw a screen as well.

**`printed_total` was guarded as `null` and arrives as `""` on a quarter of the store.** `app/src/BoxBrowse.tsx` and `app/src/CardLocations.tsx` carried the same expression — `printed_total === null ? number : ${number}/${printed_total}` — **one line below a guard on `number` that tested null OR blank**. Two emptiness tests in one function, one field apart. Measured on the owner's store: **174 of 676 numbered records store `""` there**, which is every Riftbound card, because that game prints one identifier and has no denominator. All 174 took the else branch and drew `198/219/` — a separator with nothing behind it.

**Three copies of that composition existed and no two were the same.** `ReviewQueue.tsx` folded a blank on both halves and was correct; `CardLocations.tsx` folded it on one; `BoxBrowse.tsx` folded neither and additionally printed the word `none` from inside the formatter. That is the shape `docs/DESIGN.md` would rather see merged than edited twice, and merging it is what makes the blank a one-line fix instead of a three-line one. `app/src/cardNumber.ts` is the one composer now; `numberCell` in the walk keeps the word `none`, because a fact row wants a word where a list wants nothing and a formatter that chose would put one into the cell that wanted the other.

**THE SET-CODE FOLD IS NOT IN THAT MODULE, AND THAT IS THE LOAD-BEARING HALF OF THIS ENTRY.** D55's rule — two to five letters, no digits, then one separator — is a measured shape, and `pipeline/join.py:number_index_key`'s own docstring is this repo's worked example of what a second dialect of one fold costs: the two sides agreed until they did not, and 950 rows joined nothing and blamed the export. So the shape stays in Python, published as `join.strip_set_code`, and `_repair_set_code` becomes a READER of it rather than a second copy. Re-measured for this entry across all four committed exports — 190 SV09, 786 wide Pokemon, 1,236 Riftbound, 395 One Piece, **2,607 distinct `Number` cells** — it matches **zero**; over the owner's 676 numbered records it changes exactly **10**, and all ten are the glued reads.

**Unconditional here, where the ladder asks only on a miss, and the difference is not a weakening.** D55's second safety is about a JOIN: an identifier that already matched a row is never handed to the repair, so no repair can move a card that was listing correctly. A screen has no catalog and therefore no miss to gate on — the gate is the shape alone — and the worst a wrong strip can do is draw a shorter string than the model returned, with the record, `identifications.json` and the run report's `code~:` counter all still holding the raw read. **Normalising at capture was the alternative and is refused**: D36 makes the photograph and the read the durable facts, and a store that has been tidied cannot tell you the prompt is being ignored.

**The disagreement propagated, and that is what made this worth an entry rather than a patch.** `server/capture_server.py:_agreed` returns None the moment a group's copies do not all say the same thing — deliberately, because the SKU-less group collects cards with nothing in common but the operator's query, and a number lifted off whichever copy the dict yielded first would be a confident answer about a group that has none. Five copies of Moonfall storing `198/219` twice, `UNL • 198/219` once and `UNL - 198/219` once are **not disagreeing about the card**; so the group reported no number at all while each copy's own row showed its own variant. `number_display` is agreed on the FOLDED value and the two raw fields are untouched beside it. Measured: **11 of 102 SKU groups draw no number today and 7 recover** — the four that stay silent are real disagreements (`044/106` against `044/166`, a digit misread; a copy with no number read at all) and must stay silent.

**The server composes and the client draws, with the raw pair still on the wire.** `number_display` is a fourth wire-only decoration in the shape `label`/`section`/`card` already take, added by `_card_row` and `do_inventory`, and **unconditional where those three are conditional**: a number is a fact about the card and not about where it is, so a pooled record and one whose box will not coerce both keep theirs. It is optional in `types.ts` for the reason every decoration there is — an absent key is what an older server actually sends — and `cardNumber.ts` composes the raw pair when it is missing, which is what keeps the blank-`printed_total` repair independent of the server field.

**AND WHAT THE SCREEN DREW IS SEARCHABLE, which is a side effect the fix had to close rather than leave.** Once the copies list draws `198/219` for a record stored as `UNL • 198/219`, an operator reading that row and typing it back would have been answered by a match on part of a longer string, ranked below every name prefix on the page. `_match_rank` folds the same way now, so the string the screen printed is an EXACT number match — the rank is where this is observable, which is why T7 asserts the rank and not the group's presence.

**The review queue deliberately does not get the fold.** `QueueRead` carries no `number_display`, so `#/review` composes the raw pair and shows exactly what the model returned, `UNL / 120/219` and all. **D55 was FOUND by the owner reading that string on that screen three times in one afternoon.** A queue that quietly tidied it would have hidden its own evidence: that screen is judging the read, where the inventory screens are naming a card that is already in a box.

**What would reopen this: a set code the model writes with no separator, or a game whose real `Number` cells are letters-first.** Both are D55's own stated limits and neither has changed; what is new is that a wrong strip would now show on a screen as well as miss a row.

---


## D68 — A departed card's label names the record, because two of them in one box were the same string

**`join.departed_label` ends on the store key — `Box 3 · departed · B3 #31`, spelled `3/31` as built and respelled by the amendment at the end of this entry — and every renderer draws that key in the muted register.** Built 2026-08-30, reported by the owner as *"I'm seeing two box 1's"*. There is one box 1. There were two sold copies of `Vi, Peacekeeper` in it, at stored indices **67** and **106**, and both drew `Box 1 · departed` with nothing whatever beside them to tell them apart.

**D58's label is right and is not what was wrong.** A departed card is in no slot, and printing the slot number would print the number that now belongs to its successor — a lie about a shelf. So the label drops it, correctly. **What was wrong is that the disambiguating value was already in the payload and every renderer threw it away**: `GET /search` returned `place.index` of 67 and 106 on those two rows. D58 itself draws the distinction this needs — *"The STORED index never moves — it is the `/inventory/<box>/<index>` path"* — while `Place.slot` is the countable number that shifts. The index is not a slot and printing it is not the lie D58 refuses.

**It scales with sales, which is why it was not a curiosity.** Measured on the owner's store: **11 of 12 departed records** sit in a `(SKU, box)` group that draws more than one identical row — four copies of Moonfall in box 3, three of Lightning Rush, and the two that were reported. The only thing separating them on screen was the neighbor text underneath, which is the *shelf's* fact rather than the card's and goes blank on the copies whose neighbors are themselves departed.

**The separator and the spelling are `place_text`'s, two functions down in the same module** — *and the spelling is the half this entry's amendment took back; the paragraph stands as the argument that was made.* Its pooled form already carries `· {box}/{index}` and already says why — *"the only handle left"*, and *"two pooled entries with identical lines would be indistinguishable in the report that names them"*. That sentence was true of this string as well, so this is one vocabulary rather than a second, and `where_phrase` has been writing `departed ({box}/{index})` into reports the whole time. **One formula, still**: `Position.label` is the only composer, the string travels verbatim on `aria-label`, and nothing client-side builds it.

**IT ENDS ON A KEY AND NEVER ON A BARE NUMBER, AND THAT IS FORCED RATHER THAN CHOSEN.** `PositionLabel.tsx` promotes the last `·`-part of a label to the slot figure whenever it is all digits, so `Box 3 · departed · 67` would draw **67 at 44px in the slot column of a card that is in no slot** — D58's lie reintroduced by a renderer. `3/31` fails that guard, and so does `B3 #31`.

### What the screen showed, which is why this entry has a second half

The label change alone was **worse than the defect on two of the three surfaces**, and both were found by opening the app over a copy of the owner's store rather than by reasoning:

- **The walk's left cell clipped the key off the end.** `Box 3 · departed · 3/31` measures **177px into a 169px cell**, so four departed copies of Moonfall drew `Box 3 · departed · 3…` four times — the browser cutting exactly the characters the change added. `rowSlot` now composes `departed · 3/31` from the row's own key, joining the two fallbacks already beside it (`pooled · 5/2`, `no label · 3/31`). The box is what it spends, and the walk is scoped to one shelf that is named in the panel above and in every section header — the same argument that took `Box N ·` out of those headers.
- **The copies list drew the whole string at the payload size.** A departed row measured **154.2px against the live row's 133.6px**: the least useful row in the list was the tallest one in it, and it got taller with the key. `PositionLabel` now peels the key off and renders it in the muted register — `.position-storekey`, on `.position-key`'s own `clamp` expression so no site declares a second scale — and the row is **105.7px**.

**And two things the screen showed that the label never caused**, fixed here because they are the same rows:

- **`where this sits in the box is not known yet`, under an empty track, on every departed row.** `Place.slot` is null for two different facts — a card that has left, and a box the server could not count — and `PositionBar:sentenceOf` answered both with the fault's words. Where those copies sat is known exactly. `app/src/server.ts:isDeparted` is the one predicate that tells the two apart (`located`, a null `slot`, and a label — the fault answers `label: null` with it), and the sentence now reads `no longer in the box`.
- **The bar itself is gone from a departed row on the copies list**, which is `BoxBrowse.tsx`'s existing ruling applied to the other list of the same cards: `app/tests/inventory.spec.ts` has asserted since D58 that the walk draws none, on the grounds that a bar cannot draw a card that is in no place. The two screens disagreed about the same card.

**What it does not cover, measured and left:** the copies list draws the state word twice on every departed row — once as `.card-locations-state` and once as `Inventory.tsx:Action`'s fallback — and the two can never disagree, because the second prints the first. Choosing which to delete is a D57 question and the lone-copy call site has no state span at all, so it is recorded in `docs/DEBTS.md` rather than repaired here.

### Amended 2026-08-31 — the key is spelled `B3 #96`, because a store key beside a card number is read as one

**The owner read `3/96` as a printed card number and asked what the fraction meant.** The row was one of two departed copies of `Kharox` in box 3 — the pair D68 was written for, working exactly as designed — and the card panel beside it was showing `NUMBER 114/166`. `<box>/<index>` and `<number>/<printedTotal>` are the same four characters in the same order, one of them a shelf and one of them an identity, and the copies list stacks them a row apart.

**This is the borrowing from `place_text` failing, not the key.** The pooled form earns `{box}/{index}` in a label that names a game and no box, and it is never drawn beside a printed number the way this one is. One vocabulary was the right instinct and the wrong call; the pooled form keeps its spelling, and the two never share a column because `BoxBrowse.shelvesOf` gives pooled records their own shelf.

**The box half stays, and the owner's reason is better than the width argument against it**: *"what if i searched for that card and saw that it's departed and only saw #96, would there be a way to tell what box number it's from if i was previously in say box 10?"* The copies list crosses boxes — that is what it is for — so a bare `#96` is an address missing its first half. `B` is then the one sigil no COUNT on these screens carries: `Card 17` counts cards, `Section 1 · #1–#108` counts cards, `#41` in a neighbor row is an index in a sentence that says so, and `B3 #96` cannot be read as any of them.

**Three composers moved and they are all the ones there are**: `join.departed_label`, `join.where_phrase`'s departed branch, and `BoxBrowse.departedKey` — the walk's short cell, which used to spend the row's `{box}/{index}` map key and now composes the server's spelling instead. `PositionLabel.STORE_KEY` is the reader and now matches both shapes; **a respelling that misses it does not fail, it silently draws the key as a position part**, which is why that regex carries the note it does. **Measured in the browser at the shipped 11px Martian Mono**: `departed · B3 #96` is **130.9px** against the old `departed · 3/96`'s 115.5px, inside a cell capped at `22ch` — **169.4px**, which is the same 169px D68 measured the full label overflowing at 177px. The two characters cost 15.4px and the cell has 38.5px spare, so nothing ellipsises.

**What is deliberately unchanged:** the pooled label (`Pokémon code cards · pooled · 5/12`), the `no label · 3/31` fault row, and every `{box}/{index}` that is a KEY rather than a string a person reads — the inventory map, the photo route, `<index>.jpg`. Those are addresses machines resolve, and none of them is drawn next to a card number.


---


## D69 — The order screen and the shipping lane get a route each, and the transport was measured before it was written

**Built 2026-08-30.** `#/orders` answers *which copies does this buyer get, and where in the boxes are they*, out of D63's ledger. `#/shipping` answers *which envelope does this order go in*, out of TCGplayer's own `Orders → Export Shipping` file. Two routes, not one screen with two modes. `app/src/App.tsx` now carries NINE routes — eight the owner's and one the Fulfiller's — and D66's build order is discharged: the screens exist, so the transport had somewhere to arrive.

### Two routes, because they are two questions asked at two moments

**Their inputs do not touch.** The order screen reads `inventory/orders.json` and `inventory/inventory.json` through one store snapshot. The shipping screen reads a CSV the operator uploads, which carries no line items at all — `pipeline/shipping.py:Shipment` says so in its own docstring — and which the ledger has never seen. Neither can be derived from the other, and a screen that drew both would have to explain to the operator why half of it went stale when the other half was refreshed.

**D66 named the collision this avoids and offered exactly these two options.** *"If the lane badge and the download draw on the order screen, two branches revise one file, which this repo has already paid for twice. Sequence them, or give the lane its own surface."* The lane got its own surface. That is the second option taken, not a new argument.

**The order screen therefore draws NO postage lane, and this is a prohibition rather than an omission to fill in later.** There is no `ships_in_an_envelope` field on the wire, no lane span in the markup, and adding one would not be an enhancement — it would put a second answer to D61's question on a screen with none of D61's inputs, computed from data that cannot answer it. D61 rules on the lanes, the abstention, the weight, the insurance and the PII, and this entry reopens none of it.

**The cost, named.** Two routes is two nav links, two chords and one more line in every count of screens this repo publishes — and this repo's own record is that those counts are wrong more often than they are right. The recount that goes with this entry was taken from the `ROUTES` table by reading it, not by adding one to the last number anybody wrote down.

### The paste is projected in the browser, and the server's allowlist is the backstop

**`app/src/orderPaste.ts` is the ONE place in this app that decides what leaves the browser about a purchase**, and it NAMES what it dropped rather than dropping it silently. The projection is `{source, number, placed_at, status, lines[]}` and nothing else: no buyer, no address, no city, no postcode, no payment. The dropped list is drawn on screen before the send, because it is the only way an operator can tell a working PII boundary from a broken one.

**`server/capture_server.py`'s three allowlist tuples are a BACKSTOP AND NOT THE BOUNDARY.** An unprojected paste refuses BY NAME — `field_not_settable`, naming `buyer` — rather than being stored with the extra fields quietly trimmed. Trimming was the alternative and it is worse in the only case that matters: a silent trim makes a broken projection indistinguishable from a working one, forever, and the first person to notice would be whoever read the store.

**One door.** `app/src/server.ts:ingestOrders` takes the projection as its argument and does not project. A second module composing an ingest body would be a second door onto the same wire, and the guarantee would be gone.

### The pull is body-addressed, one card at a time, and its undo lives on the receipt

**Body-addressed because an order key is `source:number` and a NUMBER may legally contain a colon.** `store/orders.py` splits on the FIRST one for exactly that reason. A key in a path segment would need an escaping rule that the one place the key is composed does not have, and the failure mode of getting it wrong is a pull recorded against the wrong order.

**One card, one press, and there is no batch control.** The route takes a LIST because `record_pull` takes a sequence and validate-all-then-write-all is the same code either way — not because a screen should offer a multi-select. Nothing in this product picks two cards at once, and D39's ruling that there is exactly ONE mass-select in the product is not reopened here.

**The undo is the screen receipt alone and never a row control.** A successful pull re-resolves the order, so the pick row it was pressed from unmounts; a control living on that row would vanish at the moment it became useful. The receipt is what survives the re-render, and it is where D28's undo window already lives on every other screen.

**The receipt reads `places[i]`, never `sales[i].card.place.label`.** The places come back AS THEY WERE BEFORE THE WRITE. A sale moves the box's occupancy (D58), so by the time the answer is composed the card is departed and its own label reads `Box 3 · departed` — a true sentence and a useless receipt.

### `GET /orders` answers from one snapshot, and `sku_unknown` draws a zero on purpose

**The list and the resolution come out of one `Store().read()`.** Two reads could straddle a sale and show a card both on hand and gone. **Only `Ledger.unfulfilled()` orders are resolved** — the ledger's own question, computed from its own two maps — and never the feed's `status` string, which `store/orders.py` stores verbatim and unvalidated so that a marketplace which learns a new word is not refused at the door.

**`resolve_all` is called with NO paperwork, and the cost is named rather than hidden.** The run-side backup would come from `cli/resolve.py:paperwork_for`, which takes ONE run, and `realign` HASHES EVERY PHOTOGRAPH OFF DISK and raises on an ambiguous digest. One bad run would take the whole screen down, and `cli/runs.py` has no list function to walk the others with. So the resolution is card-first: `sku_unknown` — the reason that fires only when a run's paperwork names a SKU no card wears — is structurally UNREACHABLE from this route and always draws a zero. **That zero is a limit of the route and not a fact about the store**, and it is reported rather than filtered out, because "nothing was short" and "nothing was checked" must not be the same payload.

### THE TRANSPORT WAS MEASURED, AND THREE PLACES IN THIS TREE SAID THE WRONG THING

**Captured 2026-08-30 off the owner's own logged-in browser**, request shapes read off an in-page interceptor and response SCHEMAS walked with the values discarded, corroborated against a third-party bridge extension the owner supplied. No credential value was read, logged or echoed.

**The order host is a COOKIE SESSION and NOT a Bearer challenge.** `order-management-api.tcgplayer.com` authenticates with `credentials: 'include'` and the `TCGAuthTicket_Production` cookie — the same `.tcgplayer.com` cookie `server/tcg_export.py:_cookie()` already names, so ONE account session serves both hosts. No `www-authenticate` header appeared on any path probed, the portal's own XHR sets no `Authorization` header, and the bridge extension authenticates purely by cookie.

**This repo recorded the opposite in three places and repeated it in a fourth**: `server/tcg_export.py`'s docstring, D64's probe table, D66's exclusion paragraph, and `docs/specs/order-pipeline.md`'s T0. All four are amended in place rather than deleted, because sound reasoning that reached a wrong conclusion is worth being able to find again — the same treatment D64 gave its own price-history correction.

**What genuinely does NOT transfer between the two hosts is the BODY CONVENTION, not the auth.** The admin host needs Knockout's `postJson` form — `model=<json>`, form-urlencoded, which is D65's shape — and the order host takes a PLAIN JSON document. A client carrying D65's form here fails, and it fails in a way that reads like an auth problem.

**Two calls, because the search result carries no SKU and only the order detail does.** `POST /orders/search` returns order numbers; `GET /orders/<number>` returns `products[].skuId`, which is the export's `TCGplayer Id`, which is `store/master.py:Card.sku`. There is no bulk line-item call. Every response is PROJECTED to an allowlist inside `server/order_transport.py` — `buyerName`, `shippingAddress`, `paymentType` and the transaction breakdown are dropped where they are parsed and are returned by no function there.

**A 403 is `order_seller_key_rejected` and is NOT an expired session.** `filters.sellerKey` is required and its absence answers 403 rather than 400, so a client that reads 403 as "log in again" sends the operator to re-authenticate over a body bug. The key is the lowercased prefix of every order number this account has: account-identifying rather than secret, so it belongs in `.env` as `PKMNSCAN_TCG_SELLER_KEY` and not in a constant.

**Verified 2026-08-30, after this entry was written**: the operator ran `order_transport.search(page_size=3)` against the live host and got three real orders back, so the stored `TCGPLAYER_STORE_COOKIE` does authenticate it and one credential serves both hosts. An agent may not read `.env` here, so the run was the operator's. **`detail` and `fetch_open_orders` are still unexercised against the live host**, and they are the half that carries a buyer's name and address — the PII projection is proven against fixtures only.

### What this does not decide

**Not the lanes, the abstention or the PII rule** — D61. **Not the ledger's two maps or the sync's one-map write** — D63. **Not whether a browser extension is ever the transport** — D66 recorded that cost and this entry does not spend it: what landed is stdlib `urllib` in one module naming one host. **And not the two write endpoints seen on the wire and deliberately not built**, `POST /orders/status-updates` and `POST /orders/<number>/tracking`, which are steps 13 and 14 and are somebody else's decision.

### What would reopen this

**A shipping export that starts carrying line items**, which would make the lane derivable from the ledger and the two-surface argument weaker. **Or a first authenticated fetch that fails**, which would mean the domain-wide cookie does not in fact serve both hosts and the transport needs its own credential — in which case `.env` grows a second name and this section's second paragraph is the one to amend.

---

## D70 — The QR is the whole identification, the product is a claim, and the card is destroyed

Ratified 2026-08-30, by measurement and by the owner's standing instruction that the physical
cards are disposed of. The code-card track's fork decisions carry the detail — **C9** (the
decode), **C10** (the product claim) and **C11** (disposal and the channel tier) — and
`docs/specs/code-cards.md` is the spec. This entry is the singles-side record of what changed
and what it costs, because three of the changes reach files the singles track owns.

**THE REDEMPTION CODE IS THE QR's PAYLOAD, SO IDENTIFICATION ON THIS TRACK IS FREE.** Confirmed
first-party by reading the official redeemer's own JavaScript bundle: it reads a `2d_code`
parameter and feeds the value straight into the redemption form. `codes/qr.py` decodes locally,
measured at the rig's real 3840x2160 frame size.
**140 of 140 physically-possible frames, zero mis-reads, 87 ms each.** Three cases are
unrecoverable — a QR under about 40 px, a 3.5 px
defocus, and glare that clips the symbol to white — and all three were established by ablation
against eleven transforms rather than assumed. Every one returns nothing.

**A MIS-READ IS FAR WORSE THAN A REFUSAL, AND THAT ASYMMETRY IS THE ARCHITECTURE.** A refusal
costs a re-shoot. A mis-read sells a stranger something that does not work, is discovered days
later, and lands in C6 with nobody able to say whether the code was bad or the read was. The
zero is therefore the number the harness asserts, not a rate.

**THE PRODUCT IS A CAPTURE CLAIM, IN D21's EXACT SENSE, AND IT RETIRES C2's OCR.** Code cards
arrive in sealed-product batches — a booster box yields 36 identical booster codes — so the
operator declares the product once per stack while the camera never has to read a SKU line.
`product` joins `game`, `set_hint`, `metadata_finish` and `rarity_claim` on `Card`, in
`CAPTURE_CLAIM_FIELDS`, in the sidecar and on the wire; `PUT /inventory/<box>/<index>` corrects
it like any other claim. **`None` is no claim and is never defaulted**, for D21's reason
verbatim: there is no ladder that infers a product, and a write-side default would make "the
operator said booster" and "nobody was asked" the same value on disk forever.

**OPENCV WAS DECLINED A SECOND TIME, AND THE FIRST REFUSAL STANDS.** This is the part worth
keeping, because the first pass got it wrong. `requirements.txt` had already declined
`opencv-python-headless` on a measurement about card SEGMENTATION. A first pass at the decoder
reversed that and took opencv for QR decoding — on a benchmark whose frames were at most
1600 px wide, **which is not this rig**: `app/src/useCamera.ts` asks for 3840x2160. Re-measured
at that size, opencv scored 72.7% at 211 ms.
**0 of 8 on a card filling a quarter of the frame, and 0 of 8 with glare** — against
`zxing-cpp`'s 100% at 67 ms. The 46 MB stays
unspent. **The lesson is not about opencv**: a benchmark at the wrong input size produced a
confident answer and the opposite of the right one, and nothing but re-running it at the rig's
real resolution would have caught that.

**THE DECODER PIN IS LOAD-BEARING.** This repo's venv is Python 3.9.6. The `zxing-cpp` 3.x line
dropped cp39 wheels, so an unpinned install resolves 3.1.1, finds no wheel, falls back to the
sdist and dies in CMake. `zxing-cpp==2.3.0` ships a real cp39 wheel. An unpinned requirement
here is a broken clone, not a newer decoder.

**THE LEDGER'S KEY IS THE CODE, WHICH CHANGES C8's FIRST BUILD.** That build upserted by
`(box, index)`, which was right for the job it was written for — C8's dispute lookup wants the
photograph, and the position names it. Under D24 the card is destroyed, so a position whose
card no longer exists is a filing reference and the code is the identity. Only a code key can
dedupe (C3's "free dedupe and structural protection against double-selling") and only a code
key can hold a reservation. The position survives as an attribute and C8's lookup is unchanged
— the code still lands on the record's `number`, so `GET /search` finds it, including on a
partial when a character is doubtful.

**DISPOSAL HAS A PRICE, AND IT IS RECORDED RATHER THAN DISCOVERED LATER.** D24 already ruled
that the cards are destroyed once the code is extracted, and the owner reaffirmed it. Research
on 2026-08-30 established what that forecloses:

- **TCGplayer, outright.** Its own policy permits code cards *attached to a physical card* and
  prohibits *"the sale of promo codes not attached to a physical card"*. No card, no
  TCGplayer — regardless of the 1,254 code-card SKUs in its catalog and regardless of this
  repo's entire join-and-emit pipeline pointing at it.
- **eBay's dispute defense.** The Money Back Guarantee excludes *"Digital content, Intangible
  goods"* and seller protection requires evidence of physical delivery.
- **Six consumer marketplaces**, by their own digital-goods bans.

**This overturns C5**, which specified shipping the physical cards precisely to buy that
protection. C5's mechanism is unavailable and what replaces it is channel choice plus C6's
replace-don't-refund. **Every researched channel came back MARGINAL** and the buy side is
actively closing; the operating rule that survives is C11's tier — a Pokemon Center ETB code
lists at roughly **46x** a booster, so the premium tail is listed individually and the bulk
floor goes out undifferentiated. `codes/products.py:is_premium` is that rule in code, and D9's
$0.40 threshold falls between the two populations, which it predicted three months early.

**NOTHING IS BUILT AGAINST A CHANNEL, ON PURPOSE.** C7's eBay Trading API call is still live
but is now deprecated in favour of a REST Message API. No channel has been executed even once,
so `#/codes` exports a list of codes and sends nothing anywhere. The cheapest experiment that
would settle the plan is one wholesale submission and one premium listing — a week's work that
replaces six marginal verdicts with two realised prices.

**REACHABLE FROM A SCREEN, WHICH IS THE HARD RULE AND NOT A FOLLOW-UP.** `#/codes` is the
eighth route: it reads a box's QRs, draws the two lanes, names every duplicate and every
unclaimed code, and commits a lane to a named order. The commit reserves permanently. The
capture screen grew the product picker in the same change, driven by `product_game` off
`GET /games` rather than by a game key written into the app.

**AMENDED 2026-08-30 BY THE OWNER: THE PILE IS SPLIT AND ONLY HALF IS DESTROYED.**
The premium code cards are KEPT physically, in a box, at tracked locations, and
will be shipped; the bulk tier is destroyed. That reverses one of this entry's own
conclusions, and the reversal is recorded rather than quietly edited.
**That sentence was true of a destroyed card and was written as though it covered the track.**
For the retained tier TCGplayer is open, and the existing `join -> emit ->
Import to Staged` path already reaches it unchanged.

**The owner also locked the channels: eBay and TCGplayer, nothing else.** The dedicated
buylist lane is closed by that ruling, which moots the $0.01-versus-$0.05 uncertainty this
entry's research left open. Lots are ~1,000 cards, shipped physically.

**THE BINDING CONSTRAINT IS ABSORPTION, NOT PRICE.**
At ~30,000 codes the pile is larger than the annual market on both venues: TCGplayer's bulk SKU absorbs 8,694 units a year across every
seller and already carries ~19,300 standing units, and the entire premium tier absorbs 924
units and $231 gross a year marketplace-wide against a pile holding roughly a year of it,
decaying at -25%/year. No pipeline change moves that number. It is why `codes/lots.py`'s most
valuable property is the guarantee a code is never committed twice across two concurrently
listed venues.

**A PHYSICAL LOT IS THE WHOLE BOX OR IT IS REFUSED.**
Both halves of that rule were found by reading generated output rather than by argument. Scoping a physical lot by COUNT commits
one thousand codes while the operator pulls a different thousand cards. Taking 1,000 of a box's
1,003 produces a correct ledger and a packing slip that lies. And the check that catches the
second has to ask what is PHYSICALLY IN THE BOX rather than what is sellable from it — a first
version asked the latter and so missed both an unclaimed code and a code already reserved to
another lot, the second of which would have been shipped to two buyers. That case was caught on
real data, not in a test.

**Still unsettled, and named rather than assumed.**
TCGplayer's bulk-lot listing needs the seller portal's Listings-with-Photos flow, which is a manual third-party UI step CLAUDE.md
forbids inside the pipeline AND asks for photographs of code cards the opsec rule forbids.
TCGplayer's own guidance permits backs and edges only, so it is reconcilable — the owner rules.
`docs/specs/code-cards.md` sections 6.1 and 9 carry the detail.

**CORRECTED 2026-08-30 AFTER THE OWNER CHALLENGED THE PHOTO CLAIM, AND HE WAS RIGHT.**
This entry recorded that TCGplayer's code-card bulk lot "cannot be listed by CSV" because bulk
lots need Listings with Photos. First-party API reads settle it otherwise. `productId 253512`
is an ORDINARY CATALOG PRODUCT — category 56, group 2303, rarity Code Card,
`sellerListable: true`, one SKU at `productConditionId 5274046` — and 26 of its 56 live
listings are `listingType: standard` carrying no image, no title and no description, holding
**28,936 of 31,493 standing units**. A CSV row produces exactly that artifact. The photo rule
is real policy and is not a mechanism, and 92% of the inventory on that SKU ignores it.

**The lane is CSV-listable and still not worth using**, which is the more useful finding. The
SKU's whole annual market is **8,694 units, about $299 of GMV**, against 31,493 units already
standing — some 3.6 years of demand queued ahead. Thirty thousand more cards take it to about
seven years.

**There is no lot structure there at all.** One SKU, priced per card, and the BUYER picks the
quantity; observed weekly sales run 1,425 / 1,100 / 975 / 734 / 700 / 558 units. So
`codes/lots.py`'s fixed-lot model is right for eBay and does NOT describe TCGplayer, and that
is recorded rather than papered over: the two venues want different shapes and only one is
built.

**Seller level gates it.** The item cap counts QUANTITY — Level 1 is 100 items, Level 2 is
500, Level 3 is 50,000, Level 4 unlimited — and Export Filtered CSV / Import to Staged is
**Level 4 only**, as is setting shipping to $0. The pipeline this repo emits is therefore a
Level 4 feature, and below that listing is UI work whatever it produces.

**The $1.49 shipping minimum fires only under a $5.00 product total**, verified across twelve
live listings. That is what makes a sub-$5 premium single net more than its own price, and it
is why a $40 bulk order carries no subsidy and the seller absorbs the postage.

---

## D71 — A card with no slot is ranked like every other, and it is the figure that goes

**`PositionLabel` composes `Box 3 · departed · 3/36` into the same treatment every live card gets, with the number column drawn empty.** Built 2026-08-30, reported by the owner in one sentence: *"I marked something sold on inventory, and it immediately deferred back to the OLD UI that I thought we totally eliminated."*

**It had. Selling a card was the way back to it.** D41 replaced a plain `Box 2 · Section 1 · Card 14` string with a ranked block of key/figure pairs, and D41's own numeric guard — *"a promoted slot is a slot NUMBER or the label renders whole"* — threw out any label whose last part was not all digits. `join.departed_label` ends on the word `departed`. So the guard refused the whole treatment for exactly the cards that had left, and `whole()` handed the raw server string back to a site whose font-size is its payload register. Two of the five sites have no CSS bail, and both drew it:

- **The walk panel drew `Box 2 · departed` at 44px, wrapped onto two lines.** That is the pre-D41 rendering, in the panel D41 exists to have unwrapped, and its own entry measures why: 27 cells of Martian Mono at 0.70em advance is 453.6px into a 448.8px track.
- **The copies list drew it at 28px as the loudest row in the list.** Live rows above it read `CARD 1` / `BOX 2 ME01 commons` / `SECTION 1`, ranked; the sold ones read as an unbroken string in the payload face. The least useful row was again the most prominent — the same failure D68 measured at 154.2px and thought it had fixed by demoting the store key.

**What the guard was protecting is the FIGURE, and refusing the treatment was never the only way to protect it.** D58 refuses the slot number for a card that has left, because that number now belongs to the card that closed up behind it; D68 adds that the store key must not take the number's place. Both are statements about the slot column. Neither asks for the plain string, and both survive here untouched — there is no `.position-num` in a departed block at all.

### The composition, which uses the vocabulary already there rather than a new one

**The state joins the path and carries the store key as its value.** `DEPARTED B3 #36` — spelled `DEPARTED 3/36` when this was built, respelled by D68's amendment of 2026-08-31 — is the same `<key> <value>` shape as the `BOX 3` above it and as the `SECTION 1` it stands in for, so a departed row costs the same two path lines a live row costs and reads in the same register. It also retires `.position-storekey`'s orphan sub-line for this label: the key is no longer a note under a string, it is the value of the thing that explains it.

**The shape that ranks is narrow on purpose, and the pooled label is what it keeps out.** A state terminal ranks only when every part in front of it is `<word> <number>`. `Pokémon code cards · pooled · 5/12` (`join.place_text`, D24) has a lowercase terminal too, but its one coarse part seams to `POKÉMON CODE / cards` — a key/value split of a phrase that has neither — so it still renders whole, at `.review-position`'s existing bail size. **A pooled card is nowhere; a departed card is in a box.** That is the line, and it is why one crossed it and the other did not.

### Two derivations, because a site-by-site answer is how this drifts back

- **In a list the reserve is the whole slot column, not the figure.** `lead='slot'` exists so every row's path starts at one x, and the shipped `min-width: 3ch` held the digits without holding the `CARD` beside them — which a figure-less row does not have. Measured: live paths at x=866.2, the two departed paths at x=827.9, a **38.3px hang**, which is exactly `CARD` at `.position-key`'s 11px (4 × 0.78 × 11 = 34.32px) plus `.position-slot`'s `--s1` gap. The reserve is now the whole column and `app/tests/inventory.spec.ts` reads both coordinates and requires one number, so the assumption that the last key is always the four letters of `CARD` fails there rather than hanging by the difference.
- **As a singleton the path re-ranks, because with no figure the path is the payload.** `clamp(11px, 0.45em, 20px)` against the site's own `--pos-slot` — 19.8px at 44, 14.4px at 32, the 11px floor at 20 — which is `.position-key`'s argument at a different rank and lives beside it for the same reason: **it is a derivation from `--pos-slot`, not a size a screen chose.** At the shipped 11px the walk panel's whole answer sat in the metadata register and read as a panel that had failed to load. `lead` is already the list/singleton distinction, so nothing new decides this; in a list the row with least to say must stay the quietest, which is the fault this entry removes.

**The dash in the empty column is `content`, not markup.** It is typography and it is `aria-hidden`, and a dash in the DOM joins `textContent` — `.browse-position` greps as `BOX 2DEPARTED B2 #4—` for every spec, screenshot diff and copy-paste that reads the rendered label. It is drawn only under `lead='slot'`: a held place is legible against the rows above it, and the same glyph beside a lone label has nothing to hold.

**The server string did not change and neither did any composer.** `Position.label` emits exactly what it emitted, `aria-label` carries it verbatim, and this is a change of VIEW — which is the property D41 named as what makes a client-side split legitimate at all. The renderer relies only on the ordering the label already had: coarse parts first, the state where a slot number would be, the store key last.

**Two specs floored the defect and are corrected rather than deleted.** `a departed card draws no number` asserted `.position-parts` count **zero** and read the raw string as text — a floor on the component *refusing* the label. `two departed copies of one card draw two different rows` read `.position-storekey`. Both were written to protect D58 and D68, both did, and both stated the protection as *the absence of the treatment*. They now assert the invariant directly: no `.position-num` anywhere in the panel, a void in its place, and the ranked path. **This is the failure mode `docs/GATES.md` step 7 already records one register up** — every check green while nothing on the commit path looks at what a human can see. Here the checks were not merely silent; they were holding the defect in place.

**What it does not cover, and why:** the pooled row still renders whole with its key demoted beneath it, which is `.position-plain`'s only remaining caller. Ranking it would mean inventing a key/figure split for a string that names no position, which is the thing D41's guard exists to prevent and which this entry narrows rather than repeals.

---


## D72 — A renumbered entry takes its citations with it, and the branch's own history is what says one moved

**Built 2026-08-30, after `docs/map.py` was found citing D67 in 24 places where it meant D69.** The order-screen entry was D67 while its branch was open; main took 67 and 68, and the renumber to D69 reached `docs/DECISIONS.md` and some prose but not the map's citations. Nine OTHER D67 citations in that same file were the real entry — the number-composition one — so no sweep could be run blind, and the wrong ones read as ordinary prose: *"the order transport (D67)"*, *"(D67) gave each its own route"*.

**EVERY DECISION CHECK THIS REPO HAD ASKS WHETHER A CITED ID EXISTS, AND A RENUMBER BREAKS NONE OF THEM.** `check_decision_ids` says the same thing about a duplicate heading in its own comment — *"the citation is then not wrong in a way anything can see — it points at a real heading, just not the intended one"* — and that sentence is exactly as true when one entry moves as when two share a number. `check_map`'s superset rule is one-directional by construction: a decision a file cites must appear in `governed_by`, so a **wrong** entry there is invisible, and prose inside a `does` string is read by nothing at all.

**Thirteen renumber events are in this repo's history and the collisions are structural.** `D50 -> D51 -> D53`, `D50 -> D52 -> D54`, `D61 -> D62 -> D64`, `D65 -> D66`, `D67 -> D69`, `D67 -> D70`, `D69 -> D71`. Several branches take "the next free number" against one base and all of them merge; D16 already carries the three-headings-at-D50 incident, which is the same collision landing a step earlier.

### The title is the identity, and the branch is the scope

**A renumber is a heading that KEPT ITS NAME AND CHANGED ITS ID**, which is the one pair no id-based check can see and the only signal that needs no judgement. `moves_across` reads it out of a sequence of states and is pure for exactly that reason: the git walk around it cannot run without a repository, and the logic that could be wrong is the part that must be testable. Five cases in `--self-test` floor it, and every id in them is real history rather than invented, so the data does not fall into the illustration problem `governed_by` already carries for `D2`.

**An entry that moved TWICE reports its FIRST id.** `D50 -> D51 -> D53` is real, and the citations that need chasing were written while it was D50; reporting the middle id would name a number nobody wrote and miss every site.

**Branch-scoped, which is what makes it quiet.** The renumber that matters is the one this branch did, and the files that matter are the ones this branch touched — a `D67` that main already had is not this branch's to move. On main, `merge-base` is `HEAD` and the row is empty for nothing. `origin/main` is the reference rather than `main`, because a worktree commonly has no local `main`: CLAUDE.md's merge discipline keeps it checked out somewhere else.

**NOT `--staged`, AND THAT IS THE LOAD-BEARING HALF.** The `D67 -> D69` renumber was committed in `9d7f473`, a MERGE — *"Merge origin/main: D67 was taken twice over"* — and git runs no pre-commit hook for a merge commit. A staged-only check would have missed it, and would have missed most of the thirteen: renumbering is what a session does while resolving a merge, by definition. Reading the branch's own commits catches it however it was committed, and the Stop hook runs this at turn end.

### Advisory, because the last step is a judgement and the list is the product

**Replayed against `9d7f473` it names nine files, and two of them were wrong.** `docs/map.py` and `app/src/Orders.css` carried the corruption; the other seven — `CLAUDE.md`, `app/src/types.ts`, `app/tests/inventory.spec.ts`, `docs/DEBTS.md`, `harness/tests/t7_store_and_seams.py`, `scripts/docs-audit.py`, `server/capture_server.py` — cite the number-composition entry and are correct. **Nothing mechanical separates those two groups**, and a check that blocked would have to be right about which is which. What nobody had was the list, and the list is what this row is.

**A file naming BOTH ids is annotated and is not evidence either way.** `docs/map.py` named both and was wrong in 24 places and right in 9; `app/src/types.ts` named both and is right in both. The finding says so rather than ranking on it, because a hint that reads as a verdict is worse than none.

### The app was never scanned, which is the second half

**`decision ids in code` walked `python_files()` and reported "citations in `.py` all resolve" — accurately, and over half the citations.** `app/` holds hundreds more in `.ts`, `.tsx` and `.css` comments, and a dangling id in one of them resolved to nothing and was reported by nothing. The scan now covers those three suffixes at the same advisory severity and for the same reason the Python row is advisory: `D2` could plausibly be a variable one day.

**Measured when it landed: zero dangling ids in the app.** So this is a floor rather than a repair — it found nothing because there was nothing, which is the only honest way to describe a check that goes green on its first run.

### What this does not decide

**Not whether two branches may take one number** — they will, and D16's duplicate-heading rule is what blocks the collision itself. This entry is about the repair afterwards. **Not whether a citation is semantically right**: an id that never moved and was wrong from the day it was typed is invisible here and to everything else, and the only reader that catches it is a human reading the entry. **And not the `governed_by` direction** — a curated entry that names a decision the file never mentions is legitimate by that field's own definition, and checking it would fire on every one.

### What would reopen this

**D100.** `_DECISION_RE` is `\bD([1-9][0-9]?)\b` and the heading pattern matches two digits, so at three digits every citation check in this file goes silently vacuous — it is recorded in `docs/DEBTS.md` rather than fixed here, because fixing it untested against a tree that has no such id is how a regex gets loosened for nothing. **Or a renumber done by rewriting history** rather than by a commit, which leaves no state pair to compare and is invisible to this.

---

## D73 — The boot header says the code changed, nothing says the data did, and only one of those is a citation error

**A screen goes stale because nobody is touching it, which is precisely when it has no traffic for a header to ride on — so the boot header's trick cannot be played a second time, and what is owed instead is a re-read at the moment the operator comes back.** Ruled 2026-08-30, after an exhaustive-deps sweep over `app/src` turned up nothing stale on the write path and made it clear the staleness this product actually has arrives from the other device.

**This is not hypothetical and the repo has the receipt.** `app/src/Fulfillment.tsx:537` says it in the first person: *"The list was read once at mount and never again, which is what let him tap Mark sold on a card the other device had already sold — the stale row was still on screen an hour later."* One missing re-read, one wrong sale, no error anywhere, and an hour of a screen quietly lying.

### Two questions wearing one name

`X-Pkmnscan-Boot` answers **did the code change under you**. `server/capture_server.py:302` computes `BOOT_ID` at import, `:308` names the header, `:7986` exposes it across origins, and `:2258` repeats it in `GET /status`. `app/src/server.ts:444` reads it off every response inside `request()` and `:437` hands it to listeners. Two screens consume it. It is a good mechanism and this entry changes none of it.

It cannot answer **did the data change under you**, and the gap is not a missing feature — it is the same fact from the other side. A restart happens *while the operator is working*, so there is traffic in flight for the header to ride. A screen goes stale for exactly the opposite reason: nobody has touched it. There is no traffic to ride, and the only way to manufacture some is the timer `app/src/ServerReloaded.tsx` records building, proving and throwing out. **A data-generation header is not a smaller version of the boot header. It is the thing the boot header's own design note explains you cannot have.**

### The sentence that is true of a process and false of a store

`server/capture_server.py:8002` argues the header is honest because *"an idle app learns nothing, and it does not need to: a stale server harms nothing until the next request, and the next request is exactly what carries this."*

That is correct about a process — nothing acts on a boot id. It is **false about a store view**, because the screen is not the only consumer of its own contents. Under D58 a card's number counts the cards in the box, so a screen that has not re-read does not show an old number, it shows a number that now belongs to a **different card**; the operator reads it, counts to it in a drawer, and pulls the wrong card. The harm lands *before* any request, which is the one condition that sentence assumes away. This repo has already measured the identical shape once, in the photo cache at `server/capture_server.py:2314` — *"the operator's reading of that screen is that the delete did not happen, and the next press deletes the card that slid in."* That was fixed with a validator on the response, not with a channel.

**The write is safe; the reading is not.** D58 is explicit that the stored index never moves, so a stale screen's write still lands on the record it names. The residue is entirely a number a human copies off a screen. One correction to the tempting narrow version of this: the phone is not immune either. `app/src/CaptureScreen.tsx:181` holds `UndoTarget = { box; index; label: string | null }` — the server's own rendered label, cached when the capture response landed — and a sale from the Mac in front of those cards renumbers it under D58.

### What is owed, and on which screens

Measured screen by screen against the rig, which is one operator with a phone over the feeder and a Mac on the desk. **Six of the ten routes are structurally immune**: `#/pricing`, `#/orders` and `#/shipping` are written only from the Mac by the operator's own hand, `#/gallery` touches no server, and `#/` is itself the second device — its positions are allocated server-side and `next_index` returns on every response, so its own writes are self-correcting. `#/runs` already polls. `#/fulfillment` is a real third-party writer under D5 and is out of scope here for D31's reason.

**`#/codes` is the sixth, and this entry counted nine against a table of ten until it was measured.** D70 routed it the same day this was written. It writes — `scanCodes`, `buildLot`, `exportCodes` — so it is not excused the way `#/gallery` is. **It is immune by `#/`'s shape, not by D24's pooling**: `app/src/Codes.tsx` renders no slot, the `box/index` it draws is D58's *stored* key behind `photoUrl` (D52), and `server/codes_routes.py` refuses a lot build on a stale claim.

**Two screens are owed something. `#/inventory` is the urgent one** — it is the D58 screen, and a capture from the phone into the box being walked changes the labels the walk draws. `#/review` wants it on next glance.

**The shape is a re-read when the operator returns to a screen, and never a re-render while they are on one — and one screen already does exactly this.** `app/src/Fulfillment.tsx:537` re-reads *"at the moments the list can have moved under it: coming back to it, and finishing a sale. Not a poll — a timer that re-reads while he is reading is a list that reorders under his thumb."* That is D28's argument reached independently from a real incident, and it is the pattern this entry generalises rather than invents. What no screen in the app can do is notice a write landing while the operator sits on it — the hour-long case above.

**Within one browser, "coming back to it" is already free.** `App.tsx` renders `<route.view />` against a table keyed by hash, and all ten views are distinct component types, so every route change unmounts the outgoing screen and every arrival is a full re-read. The gap is not navigation. It is the screen nobody is navigating away from. D28 rules that the list stops moving under a finger already travelling toward a number; that ruling is untouched here and `#/review` is named as prohibited from any automatic mid-session re-render. A notice with a control to press was the alternative and is refused — `docs/DESIGN.md` bans acknowledgements, and the one screen D28 reopened that ban for reopened it on grounds found inside the rule.

### What a signal would cost, banked rather than built

`store/session.py:125` is the single funnel every mutation passes through: exclusive lock, re-read inside it, five JSON files written whole on a clean exit. A counter incremented there covers a capture, a sale, a review answer, a retirement, a divider, an order ingest and a pull without any of them being taught about it, and there is no second door to forget.

**Coalescing is a requirement and not a refinement**, and the number that settles it is already recorded: `docs/GATES.md:884` puts the feeder at a median 623 ms over 84 intervals. Anything that fired per generation would fire twice a second for the length of a box — furniture inside a minute, and worse than silence, because it teaches the operator to ignore the one that matters. A monotonic counter can be compared and coalesced; a random id like `BOOT_ID` cannot.

### Why not a live connection, measured rather than assumed

The owner asked whether this should be less of a static app. It was costed properly rather than declined on precedent, and **the objection is not capacity**: `server/capture_server.py:8583` is a `ThreadingHTTPServer` with one thread per connection and no pool, so a stream starves nothing.

It is the drain. Every verb funnels through `_dispatch`, which counts requests in flight; a stream that sits inside it never leaves, so every save of a watched Python file becomes a 35-second stall, a 40-second supervisor grace, a SIGKILL, and a `check history.jsonl` warning about a store that is fine. D53 restarts the server many times in a working session. There is a second cost that is worse for being quiet: `app/tests/cursor.spec.ts:138` waits for `networkidle`, which an open stream never reaches, and the wait is inside a `.catch` — so the suite would stay green and get roughly three and a half minutes slower with nothing on screen to say why. A WebSocket adds a dependency to the one process that may never need `make venv`, to buy a duplex transport for a simplex problem.

**None of that argues against liveness; it argues against a persistent connection as the first thing to build.** The header-plus-return-to-screen shape contaminates no test, by the mechanism that already makes the boot header safe: a stubbed route sends no header and is therefore silent by construction.

### The citation repair

`ServerReloaded.tsx` opens by citing D53 for the boot id. **D53 does not contain the words `onServerBoot`, `X-Pkmnscan-Boot`, `boot_id`, `BOOT_ID` or `ServerReloaded` — not once.** Checked three ways: a case-insensitive search of this file for "boot" returns five hits, every one `launchctl bootout`, "imported at boot", "will not boot" or "fails to boot"; the identifiers appear in `app/src/`, `server/capture_server.py` and `docs/DEBTS.md` and in no ref's `docs/DECISIONS.md`; and D53 is byte-identical between this worktree and main.

**Seven sites cite D53 for the header or the notice and now point here**: `app/src/ServerReloaded.tsx:1` and `:18`, `app/src/ServerReloaded.css:1`, `app/src/server.ts:416` and `:446`, `app/src/types.ts:235`, `app/src/Shipping.tsx:147`. **Five are correct and are left alone** — `app/src/types.ts:230`, `app/src/App.tsx:787`, `server/capture_server.py:8002`, `server/order_transport.py:542` and `server/tcg_export.py:102` all cite D53 for the watcher, the supervisor or the restart, which are genuinely D53's.

The mechanism is adopted rather than re-argued. Every rule in `ServerReloaded.tsx`'s header stands unchanged: no poll, silence on absence, never on first sight, `role="status"`, expires on its own, hung off `hasChrome` so it never draws on the Fulfiller's view. What changes is which entry it stands on.

### What it costs

- **`docs/DEBTS.md` records that the reload notice has no automated case.** Three were attempted; two passed against a build with the notice rendered unconditionally and were deleted rather than kept, and the third failed outright. Anything built here inherits that difficulty, and the honest move is the one already made — name what is verified and what is not, rather than ship a green row that asserts nothing.
- **A return-to-screen re-read is per screen by construction.** It does not preserve `app/src/server.ts` as the only module that participates, which is a real cost the one-observation-point rule was bought to avoid. Stated rather than denied.
- **`markSold` and `undoSale` take `(box, index)` and carry no aim check.** Only `removeCardInPlace` and the order pull are `capture_id`-aimed. The wire does not refuse a stale press, so nothing here may be argued from the belief that it does.

**D13 is not reopened.** The store, the photographs and the truth stay on this Mac.

**BUILT: the re-read-on-return idiom, on one screen only** — `app/src/Fulfillment.tsx:537`, argued there from the incident above, plus the unmount-on-navigate that makes arrival a re-read everywhere. **RECORDED: this ruling, the two-questions distinction, the citation repair, and the terms a signal would have to meet.** **NEITHER: the generation counter, any signal that reaches a screen nobody is touching, the same idiom on `#/inventory`, and a test for any of it.** The distinction matters because the built half is the half that only helps when the operator was already going to act.

**What would reopen this: a second pair of hands.** Every narrowing above rests on one operator moving between two devices. A real Fulfiller working `#/fulfillment` while the owner sells from `#/inventory` is two people writing at once, and the return-to-screen shape is too slow for it.

---



## D74 — A document is checked as a document, and every markdown file is linted rather than the four a session loads

**Prose checking is scoped to what a file is, not to how much of it a session reads.** Ruled 2026-08-30, after a sweep of `docs/` found two defect classes that no row of `make docs-audit` was structurally able to see.

**`make vale` ran over four files while `.vale.ini` always said `[*.md]`.** The target was the narrow half of that disagreement, so `docs/specs/` and `docs/design-refs/` had never been linted: **35 `AmericanSpelling` errors** had accumulated there, none reachable by any check in this repo. The file list is now `git ls-files '*.md'`, so a new document is linted the day it is committed rather than the day somebody remembers to add it to a target.

**D60's scope is an argument about density, never a license to leave prose unspelled.** That entry rules on the four docs because they were `@`-loaded and cost tokens on every turn. Spelling costs nothing to check and is wrong in the same way everywhere, so the two scopes were never the same scope and the target had silently conflated them.

**The vocabulary grew by 140 terms and was reviewed rather than blanket-accepted**, the way its first block was. Two candidates were checked in context before being let in — `evid` and `src` are shorthand names inside an algorithm description, and `moded` is a deliberate verbing — and the 35 spelling errors were fixed rather than accepted, which is what happened to `rasterises` the first time round.

### The one label that was itself misspelled

**`raw colour` became `raw color` on the owner's instruction, and the rename stopped at the row.** A row label is published prose — it is printed by `make docs-audit`, cited in `docs/DEBTS.md`, and named in the comments the `numbering in code` row polices — so a label spelled against the rule this entry sets was the rule contradicting itself in its own report. The label, `check_raw_color`, `_RAW_COLOR_RE`, the row's summary and its self-test messages all moved together.

**It stopped there deliberately.** `colour` appears about 120 times across 29 source files, in comments and identifiers, and `.vale.ini` already records that widening the spelling rule to source *"would split the spelling inside single files and is a decision nobody has argued"*. This is not that widening: it is one published label brought into line with the report it appears in. `COLOUR`, the token-kind discriminator at `scripts/docs-audit.py`, is untouched — it is compared with `==` and never reaches a message, so it is not prose.

### `doc hygiene`, and what it is for

**Every other row reads a document's assertions; this one reads the file.** It is advisory, and it asks three questions decidable on the committed tree alone: a line that reads as an instruction to an editor, a second level-1 heading, and a `path:line` citation past the end of its file.

**It exists because two real defects were invisible to a green audit for eight days.** `docs/specs/capture-server.md` carried *"Leave lines 37-38 exactly as they are. Insert a blank line and this blockquote after line 38"* inside a paragraph — and the paste that put it there deleted the sentence it was preserving, leaving a decapitated clause. `docs/specs/ui-research.md` was two documents in one file. Neither is a false claim about the code, so no row asked.

**Advisory rather than blocking, and the second condition is why.** All three are provably true of the tree, which is D16's test for a blocking row, but *true* and *wrong* part company on a duplicate title: a file that deliberately carries two is a judgement, and a blocking row would settle it by fiat. What would earn a promotion is a second instance of the instruction case reaching main.

**Mutation-tested three ways** — the committed instruction, the second heading, and a citation past a file's end — each caught, and the row green when all three are reverted.

### The check that was prototyped and refused

**A `reachability claims` row was built, measured, and thrown out the same hour.** It would have paired a registered route from `ROUTES` with a nearby not-built phrase, and it was aimed at the sharpest staleness this sweep found: `docs/specs/shipping-export.md` said no route, client function or screen reached its modules on the same day D69 gave them all three.

**It fired 13 times and every one was a false positive.** Sentences like *"No history on `#/inventory` — that is the ruling above, not an omission"* are claims about a feature inside a route, not about the route's reachability, and nothing separates the two without reading the sentence. **A permanently-lit advisory is worse than a silent check**, on this repo's own finding from the committed-staleness row it dropped for the same reason: one row stuck on teaches sessions to skip exit 2 against every row that uses it.

**The staleness it was aimed at is a process fact rather than a tree fact.** Both of this sweep's worst findings — that one and D73's route count — came from two branches landing on one day, each correct against a tree the other had already moved. Nothing readable from a single commit can see that, which is why it is recorded here and in `docs/DEBTS.md` rather than guarded.

### What this is not

**It is not a claim that the docs are now current.** It is two mechanisms and one sweep. `docs/DEBTS.md` cluster 1 still holds the five docs-to-code checks that walk one way, and this entry does not touch them — they are blocked on a decision about advisory severity that this row's existence does not settle.

---

## D75 — A detector that cannot say "wrong" is asked a second question, and the crop is refused rather than trusted, and the shape correction reaches both crop paths

**`geometry.detect_card` answers "not found" honestly and has no way to answer "found the wrong thing", so the crop path asks the frame instead: a crop under 30% of it that keeps under half its detail is not cut, and the whole frame is sent.** Ruled 2026-08-31, from the owner's own screenshot of `#/runs` drawing a crop rectangle over a card's rules-text panel and reporting it as the payload.

**Numbered D75 because D74 was taken while this branch was open** — `origin/main` carries "a document is checked as a document" at that number, merged 2026-08-30. D72's rule applies to a renumbering, and this is not one: nothing was published at D74 here to move.

### What was measured

Not a guess about the detector, and not a tuned constant. `detect_card` was run over **all 867 photographs in the owner's three real boxes** — box 1 (133 Riftbound), box 2 (543 Pokemon), box 3 (191 Riftbound) — with the crop rectangle `identify/images.py:crop_rect` would cut from each.

**It returned a box for every one of the 867 and refused none.** Nine were wrong, all in box 3, and every one of them the same shape: a card-shaped rectangle **inside** the card — the rules-text panel, the artwork frame — carrying a card's aspect, a passing border score and nothing to distinguish it from a hit. Two of the nine are the frames in the owner's screenshots.

The probe that decided the design is that on those nine **the whole card is not among the candidate rectangles at all**. The largest candidate on `box3/0024` is 0.21 of the frame against a card filling roughly half of it: those cards sit in a stand with a stack behind them, so the card's outer border is against another card rather than against a ground, and the strongest four straight edges in the frame are the ones printed on it. **This is therefore a refusal and not a detector fix.** Re-scoring, preferring the outermost candidate, or widening the peak search cannot choose a rectangle that was never a candidate.

### Why two measurements and not one number

On the padded rectangle that is actually cut:

| | area of the frame | detail the crop keeps |
|---|---|---|
| 858 correct | 0.300 – 0.988 | 0.438 – 0.995 |
| 9 wrong | 0.068 – 0.270 | 0.152 – 0.435 |

**Neither column separates them on its own.** On area the gap is 0.270 to 0.300, and box 1's smallest correct crop sits **exactly** on 0.300 — box 1 is shot further back and its correct crops are genuinely small, the same size as box 3's wrong ones. On detail the gap is 0.435 to 0.438, under a percent. A threshold in either gap is a number fitted to 867 frames from one rig, and this repo has a name for that: a margin that is exactly sufficient on the worst frame measured is not a margin.

So the rule is an **AND**, and each leg covers the other's boundary. Over the measured set it refuses all 9 wrong crops and **none** of the 858 correct ones, and the legs are doing separate work — 27 correct crops fall under the detail line and are kept by the area leg.

**The second axis is detail rather than a tighter aspect gate, because detail is what is unmistakably true of the failure.** The rest of the card is still outside the crop: sharp, structured, and thrown away. A crop of the subject keeps the subject. It is a ratio over the same absolute-luminance-gradient signal `geometry/detect.py`'s border search is built on, so the guard and the detector read the same picture, and a dark backdrop or a busy tray cancels out of the numerator and denominator together.

**A plain floor was tried and taken out**, and it is recorded because it is the guard a person reaches for first. "Refuse anything under 10% of the frame, whatever else is true" catches nothing the AND does not — every one of the nine is under both lines — and it has a case where it is simply wrong: T6's own `_scene(scale=0.55)` is a small card correctly found on a plain mat, 8% of the frame, keeping 94% of its detail. A second rule that adds no catch and subtracts a correct crop is not redundancy.

### Erring toward refusal is the cheap direction

This is what lets a threshold sit near a boundary at all, and it is `geometry/detect.py`'s own argument read one register up. **A refusal sends the whole frame**: more image tokens, the reading every run made before `--crop` existed, and a correct answer. **A false accept sends a picture with the collector number cut out of it** and gets a confident answer about nothing — the failure D23 says no confidence threshold catches, and the one `card_rect`'s aspect correction was written for after box 2 sent 544 cards under a flat pad and 38 came back with no number at all.

### Where it lives, and what it is not allowed to be

`identify/images.py:crop_refusal`, called from `prepare` — **the one place the bytes are made** — so nothing downstream can hold a box that was declined and cut with it anyway. `card_crop` and `crop_rect` are untouched: they remain the pure cut and the pure rectangle, and T6's identity between them still holds.

**It returns a sentence, never a flag**, because every caller has to say this out loud and none of them can explain a true-or-false:

- `Prepared.crop_refused` carries it, so a run cannot report itself as having cropped while sending whole frames.
- The preflight prints the count **apart from** `no card found` and then the reasons themselves, before any money. The two are not the same fact: nothing found is a photograph to look at, and a box refused is a detector that answered confidently and wrongly.
- `#/runs` draws no rectangle and shows the sentence under the picture, which is the same treatment `band_absent` gets and for the same reason — the pipeline's words, not the screen's summary of them.
- The closing report lists them under `unfit crop`, kept apart from `not detected`.

**The crop-retry path gets the same guard, for a sharper reason.** A retry happens after a reading came back malformed or unsure, and its bands are cut out of this rectangle — so a box that is really the rules-text panel sends an enlarged photograph of rules text and calls it the collector number. §4.5 rung 3 sends that card to a human instead.

### What this does not establish

**One rig, one day, 867 frames.** What is established is that these two numbers separate these two populations. What is **not** established is a rate at which detection goes wrong: nine is nine of the owner's own boxes, not a percentage of anything, and every one of them is Riftbound in a stand with a stack behind it. Read it exactly the way `docs/GATES.md` says to read the border search's 53/53 — that number is a rate at which the card is FOUND, and a wrong box and a right one both count as found, which is why it could stand for eight days beside this.

### Amended the same day: the correction was on one crop path and not the other

**A second defect on the same path, found by another session tracing how `identify` recovers a badly-cropped card, and routed here by the owner.** `card_rect`'s aspect correction — restore the height a real card of this width would have, because the border search comes back systematically short at the number end — was applied to the primary image `--crop` sends and to the run panel's band preview, and **not** to `geometry/crop.py:registered_card`, out of which every crop-retry band is cut as a fraction.

**It was reported as read off the code and not observed. It is observed now.** Over box 2's 543 photographs the registered card's aspect ran to a median of **0.789** against a real card's 0.716 — the same 0.790 median `card_rect` already recorded — which puts `NUMBER_BAND`'s bottom edge at **0.953 of a card-shaped rectangle at the median and 0.935 at worst**. On **`box2/0340.jpg`**, whose box bottom sits at 0.756 of the frame where its neighbors sit at 0.805, the number band contained the weakness/resistance/retreat row and **no collector number at all**. That is the last automatic rung enlarging the wrong strip to 600px and answering confidently — the `0342` failure mode again, reached from the retry rather than from the first pass.

**The fix is one computation, not a second copy**, which is the rule `crop_rect`'s own docstring states. The correction moved down into `geometry.corrected_bounds` with its whole argument, because `geometry/` may not import `identify/` and that layering is exactly why the retry path could not reach it. `identify/images.py:card_rect` is now a delegate and keeps its name: several entries cite it, and renaming it to save one line would move a docstring they point at.

**Clamped to the canvas in `registered_card`**, because the correction only grows and a card near the frame's edge would otherwise be cut against nothing and padded black — a black bar pretending to be cardboard moves every band below it.

**What the fix does not do.** It is **symmetric**, so a box short only at the bottom — which `box2/0340.jpg` is — recovers half its deficit and no more. `CardBox` reports no per-edge confidence, and attributing the whole correction downward would be inventing a fact; the entry this amends is the one that already says so. 0340's number went from outside the band to inside it at the band's edge, and sixteen box-2 bands sampled evenly across the run all contain their number after the change.

**BUILT**: `geometry.corrected_bounds` and both callers through it, the aspect wired from the registry to `crop_regions`, and T6's regression case — which is a real one: a box 10% short at the bottom holds 0.088 of the number box in its band before the fix, under T6's 0.10 floor, and 0.157 after.

**BUILT**: `crop_refusal` and `detail_share`, the guard inside `prepare`, the guard on the crop-retry path, the two figures the preflight prints and its reasons, the closing report's `unfit crop`, `crop_refused` on the preview wire, and the sentence rendered on `#/runs`. **RECORDED**: this entry, the two populations in `identify/images.py` beside the constants, and `docs/GATES.md`'s T6 section. **NEITHER**: any change to `geometry/detect.py`, a rate for how often it is wrong, and a second detection method for a card whose border is against another card — which is the only thing that would actually recover those nine crops rather than decline them.

**What would reopen this: a rig whose correct crops are genuinely small.** Both numbers are fractions of the frame, and a camera moved back far enough would put correct crops under both lines and send every card whole. That costs money rather than accuracy, and the figure the preflight prints is what would say so — a nonzero `box unfit to crop to` on a box where the crops look right is this entry asking to be re-measured.

---

## D76 — A hint is evidence about its own card, and how wide to ask is a per-game rule

**A set filter needs the box to be unanimous, and the game decides whether to narrow at all.** Built 2026-08-31.

D65 scoped the export by the set hints the box's own cards carry. The reasoning — widening is always safe, narrowing is not — is right, and the rule built from it counted the wrong thing.

### The defect

**It gathered the hints that existed and never counted the cards carrying none.** A set of hint strings has already forgotten how many cards there were, so `hints` was non-empty and the fetch narrowed, whatever fraction of the box had spoken.

**One hinted card in a 200-card run scoped the whole export to that one set.** Reproduced before the fix on a synthetic Riftbound run: `SetNameIds` came back `["77"]`, 199 cards had no catalog row to match, and each would have queued `no_catalog_row`.

**Nothing could see it.** The fetch reported success. D65's own positive check passed, correctly — it asks whether the sets that were asked for arrived, and Origins did arrive. The check cannot ask about sets nobody requested, which is exactly the failure. The receipt named the scope only after the file was on disk.

**The owner hit it on a box sorted by rarity.** Some cards carried a set hint, most carried only a rarity claim, and the expectation was the whole category — which for that game is the correct answer for a second reason, below.

### Unanimity, not presence

**A hint is evidence about the card that carries it and about no other card.** So a set filter is legal only where every card of the game in the run carries a hint and every hint resolved. Anything less widens to the category and says which condition failed.

**`server/pipeline_routes.py:_scope_counts` returns counts rather than a set of strings**, because `cards` and `hinted` are the two numbers the rule turns on and the old shape could not answer the question. One counter serves both the fetch and the preview, so the panel cannot describe a scope different from the one the button sends — the rule `_parse_preflight` already follows about not recomputing a figure the operator is reading.

### How wide to ask is per-game

**`export_scope` in `pipeline/games.py`, and only `riftbound` earns `category`.** The committed export is the entire English catalogue in one 10,078-row, 1.6 MB file, so there is nothing a set filter buys there and a real hazard in spending one.

**Every other game keeps `sets`, and the default is `sets`** — the value that cannot be wrong by omission, since it still widens unless the cards are unanimous. `one_piece` is the likely next `category` and stays `sets` until a whole-category download is measured, on the same asymmetry that module already uses to decide how far a matrix may be narrowed: its committed export is three sets out of many.

**`pokemon` is not a candidate.** 220 sets in the live category picker, and the widest file this repo holds is four of them.

**The audit row is blocking and provable from the literal**: the value is one the registry publishes, and `category` cannot be authored for an entry naming no `tcgplayer_category_id`.

### Three voices, and the screen says which one spoke

**The operator outranks the game, and the game outranks the cards.** Explicit `set_ids` is somebody making the claim about the box that the inference was trying to reconstruct, so it narrows a box carrying no hint at all; `scope` picks the axis; the registry rule is next; the cards' unanimity is last.

**`GET /pipeline/runs/<name>/scope` draws the lever's position before it is pulled.** Free, presses nothing, and takes the same three fields the fetch takes. It answers a mixed-game run with a LIST where `POST .../export` refuses `game_required`, because a screen that must ask which game cannot draw the picker from a route that refuses without one.

**It degrades the way `GET /tcg/sets` does.** Resolving a hint needs the portal, so a stale cookie leaves `asked` null with the reason named — and the counts, the game's rule and the reason it would widen are local and still draw.

**`asked.reason` is on the receipt as well as on the control**, because a scope is only correctable by somebody who can see which voice chose it, and a receipt reporting the scope without the reason is what let the one-hinted-card narrowing read as a correct answer.

### What was deliberately not surfaced beside it

**`--rule` and `--basis` stay off `#/runs`.** D49 makes `decisions.json` the one place a pricing answer is written and `#/pricing` the press that writes it; `check_pricing_presets` exists because a second place to say `rule` already produced 48 cards about to list at a price nobody had chosen. A third would be that defect by a third road.

**`--review-below-confidence` is surfaced**, because it is a routing question rather than a pricing one, it is written nowhere else, and it was reachable only from a terminal.

### Three fields of the request are instructions, and they are guarded as such

**`ExcludeListos` is `True` — listings with photos are excluded.** The owner's standing instruction, 2026-08-31, and it stands on that rather than on an argument this repo can check.

**What the flag does to the file is NOT measured, and the entry says so rather than reasoning past it.** The name is read off the portal's own bundle and nothing here has run the same request both ways to see what moves. The plausible mechanism — a seller-photo listing is usually a specific copy at a premium, so excluding them changes what the low-price columns aggregate — is a guess, and the export carries four price columns (`TCG Market Price`, `TCG Direct Low`, `TCG Low Price With Shipping`, `TCG Low Price`) that are TCGplayer's own, with no published rule for which listings feed them. Recorded as an open measurement rather than dressed as a finding: one authenticated fetch each way, diffed, would settle it.

**It shipped `False`, and no decision ever chose that.** D65 captured the request body off the owner's own browser submit, so this field arrived carrying whatever the Pricing tab's checkbox happened to be set to that day. Eleven of the fourteen fields are transcription of somebody else's form; three are decisions, and they were sitting among the eleven with a comment beside each.

**Nothing downstream could ever have caught it, which is what makes it a guard rather than a comment — and is also why the mechanism above is unmeasured.** D64 measured `Photo URL` empty in all eleven exports, filtered and unfiltered: this axis leaves no trace in the file it narrows, so the file cannot be read for what the flag did to it. A wrong value gives a clean join, a clean reconcile and a green `make check`, indefinitely. The same blindness is what makes the guard necessary and the measurement expensive.

**So the three are hoisted into `STANDING_FILTERS` and spread last**, where a re-capture of the portal's body cannot silently paste over them, and `scripts/docs-audit.py`'s `export request` row blocks the commit on any value that has moved — naming the instruction rather than the literal, because somebody who has just changed a value already knows what the literal is. T7 asserts all three on the wire, which is the half a literal check cannot reach.

**The first fetch after this lands will refuse `export_narrower`, correctly.** It removes rows a previous export carried, which is the guard doing its job; `accept_narrower` is the honest answer once, and the baseline moves with it (retired 2026-09-02).

**The rarity and condition axes stay unspent.** `Scope` carries `rarity_ids` and `condition_ids` and both remain empty: D64 measured that a condition filter thins a number's rows and that D3 rung 2 then decides a card from whichever row survived, and a rarity claim is per-card and would inherit the exact partial-claim defect this entry fixes.

---



## D77 — The pipeline's rows can be the wrong card, so the export is reachable from every entry — asked for, never offered unasked

**Built 2026-08-31, and the owner found it the same way they found D46: by asking why the screen would not let them say what the card is.** *"How come in review queue there's no option to hand revise an answer? why do i only get to pick from your suggestions"* — over a screenshot of box 3 card 66.

**The entry in that screenshot is the whole argument, and it was the ONLY open entry in the store.** 152 queue entries across `review.json` and `parked.json`, 151 already cleared, one waiting — and that one could not be answered:

- read: `Nasus, Ascended`, number `8/298`, no set hint, rarity claim `Epic`;
- candidates: `Get Excited!` at `008/298` in Origins, Near Mint at $0.07 and Near Mint Foil at $0.29;
- photograph: Nasus, `046/166`, VEN;
- and the card's own row, in the same export the entry was joined against: **`9405493`, `Nasus, Ascended`, `046/166`, Near Mint Foil, Epic, $0.74.**

The number was misread, and `008/298` is a **real key** in that export belonging to a different card. So the join found rows, confidently, for something else. `rarity_claim_mismatch` is exactly the reason D23 built for this — its own comment calls it the one that catches "`051/197` for `031/197`, a CONFIDENT answer no confidence threshold fires on" — and it fired correctly. The screen then offered the operator the wrong card's two rows and nothing else.

**D46's guard was the right guard against the wrong question.** It let a human point at a catalog row only for an entry with **zero** candidates, on the reasoning that "a card the pipeline found rows for has its answer on screen already". That makes *the pipeline offered nothing* the test for whether a person may overrule it, and the test that was wanted is *the pipeline is wrong* — which is not a thing a queue entry can know about itself. The two coincided for as long as nobody looked at a card where they came apart.

**What is widened is which entries the flag reaches. What it checks is untouched.** `_answer_target` honours `from_catalog` for any entry now; every line of the guard beneath it is the same code:

- the SKU is re-read out of **this card's own export**, inside the write lock, via `_catalog_for_card`;
- the **condition comes off that row and never off the request**;
- a SKU the export does not carry refuses as `sku_not_in_catalog`.

So the property D46 protected — no string a client sends becomes a listing on its own — is unchanged, and it never depended on the candidate count. `GET /review/<box>/<index>/catalog` did not move at all: it was never gated, because searching an export the operator is already looking at was never worth refusing.

**The anti-laundering refusal stands where it always stood.** An answer that does **not** set `from_catalog` still may only name a row the pipeline offered, and still refuses as `sku_not_a_candidate`. What the flag buys is not permission to send any SKU; it is the claim *a human went and found this row*, and it is paid for by the server re-reading the row.

**D46's second argument is kept rather than overturned, and `looking` is the whole of the difference.** That entry refused to fetch a catalog beside a good list of rows: "a second, looser list beside a good one is how a screen teaches you to stop reading the first." True — and it is an argument about what is drawn **unasked**. Nothing changes on arrival at a card with rows: no fetch, no panel. The export appears only after `L`, and a list the operator pressed a key to see is one they have already decided the first list failed to answer.

**One list at a time, and that is a correctness rule rather than a layout preference.** Both lists are answered on digits, so a screen showing both would make `1` mean two rows. Opening the export **replaces** the pipeline's rows; Escape or `L` brings them back, writing nothing. The digit handler picks its list from `showCatalog` — the same flag the renderer branches on, read rather than re-derived. It read `candidates.length > 0` while the two lists could not coexist, and left as it was that is a **silent mis-write**: the operator sees the export's third row, presses `3`, and the entry's third row — a different card, which is why they went looking — lands on a real position with no refusal, because that SKU is a perfectly good candidate. Asserted as its own browser case.

**`from_catalog` on the history line stops carrying a second condition, and only now does it mean what its name says.** It was written as `from_catalog and not governing.candidates`. Under D46 those could not come apart, so the extra clause cost nothing; now it would omit the flag from precisely the answer that most needs it — the one where the pipeline had a confident offer and a human overruled it. After the write there is no other evidence which happened.

**The group route still does not pass the flag, and the REASON changed rather than the rule.** The old reason was arithmetic — a group is uniform over one shared candidate row, so a zero-candidate entry could never qualify. Widening retires that, so the real one has to be stated: a catalog row is found by a person looking at **one** photograph, and D29's group answer is a claim about a set of cards nobody is looking at individually. Applying a row found for card A to fifteen others is this guard's own failure mode arriving by the one door that skips the looking.

**`rarity_claim_mismatch` got a sentence, which it had never had.** `reasons.ts` gave it a chip label the day the reason shipped and `ReviewQueue.tsx`'s `sentence()` never got a case, so the screen drew *"a reason this screen has no sentence for"* over the one open entry in the store. It is the only reason the pipeline emits that can mean **the candidate rows themselves are the wrong card**, and nothing else on screen said so. It does not quote the claimed rarities: `QueueEntry` records the read and the candidates and not `rarity_claim`, which lives on `master.Card`, so naming them would need a schema change.

**Measured, on the card that produced this.** `_catalog_matches` run against that run's own export with the entry's read name returns **two** rows, correct one first: `9405493 · Nasus, Ascended · 046/166 · Near Mint Foil · $0.74`, then the alternate art at `046a/166 · $3.26`. The mechanism that fixes this card already worked; the only thing between the operator and it was `candidates.length === 0`. Answering the wrong offered row would have listed a $0.74 card at $0.29 under a different TCGplayer product.

**What would reopen this: `from_catalog` appearing on entries whose offered rows were right.** D46 named the same tripwire pointing the other way and it still holds — if the flag starts landing on cards a better join would have placed, the fix is upstream. This entry adds the near side of it: if the flag starts landing on entries **with** candidates at a rate that is not rare, the number read is the thing to fix, not the screen. Box 3's read is already the second measured instance of that (D55, 7 of 39 across three separators), and this is the third symptom of one defect.

## D78 — A run's reason for adding nothing is a heading, the rows under it sink, and a hold sinks on the reopening

**Built 2026-08-31, on the owner's ask, over a screenshot of `#/pricing` on a Riftbound box.** Two sentences, one after the other: *"can we have it so that 'every copy in this run is already listed or sold' rows go to the bottom?"* and *"instead of each of those rows having that quoted subtext, instead it's a header and these rows fall under it"*. They are one change, and the second is what makes the first worth doing.

**What was on that screen.** Of the eight LISTED rows visible, five carried `every copy in this run is already listed or has left the box` in their own right margin — including the top two, at $39.10 and $30.93. The list is sorted market-descending (`cli/cmd_join.py:_pricing_table`, and it stays that way), so the run's most expensive **non-questions** stood where the eye starts, five copies of one sentence ran down the column, and the rows that actually wanted a price were read around them.

**The rule: a row this run can add nothing for sinks to the bottom of its own section, under a heading naming why.** Inside every group the market order is untouched. The sections are untouched — nothing crosses one, because `bucket` is still decided by the Market cell alone.

**Grouped by the SENTENCE, not by `at_cap`, and that is D59 held to.** `pipeline/join.py:SkuMatch.nothing_to_add` composes three of them — every copy already listed or gone, at the live cap, or held by an import this pipeline has not seen land — because they have three different remedies. Three headings, then, in first-appearance order down the wire; never one bucket of leftovers under a word like *skipped*, which would be the client re-deciding that the three are the same thing. A `pricing.json` an older join wrote carries `at_cap` with no sentence beside it, and those rows group under the bare fact, which is all `at_cap` means.

**D28 is why this may be done at all.** The list must not move under a finger already travelling to the next field. Every input to this order — `bucket`, `at_cap`, `nothing_to_add` — is written by `join` and read off disk, so nothing the operator types on this screen can move a row out of its group, the same way nothing typed can move one between sections. The heading is deliberately not `sticky` for the same reason: a heading that detaches and rides the scroll is that motion arriving from the other direction.

**The advance now steps the order that is DRAWN, and the bug it would otherwise have been is worth recording.** `Enter` and the arrows walked the wire array. That was correct only by coincidence: the wire is market-descending with `None` last, which puts the three buckets in the same order the three sections are drawn in. Sinking a group moves a row within its section and ends the coincidence — stepping the wire would have sent the focus from a row near the top down to one drawn at the bottom of the section and back up again, on a screen whose whole gesture is type, Enter, type.

**The row's second line is the operator's own note now, and it gained a string it used to swallow.** The reason won that line over the hold's note, on the argument that the reason is the fact about the run and the note is an aside. With the reason a heading, a row that is both at the cap and withheld draws the note — the one string on that line nothing else on the screen holds a copy of. The 13px reservation that keeps every row the same height is unchanged and still carries the machine token beside it.

**What would reopen this: a group with one row in it, over and over.** The heading costs a line, and it buys nothing over a row's own margin when it covers a single row. Measured on the shape that produced this — five rows, one reason — it is plainly right. If a real run draws three headings of one row each, the answer is a threshold, not a return to the subtext.

### Amended the same day — a held row sinks too, and it sinks on the REOPENING

**The owner, an hour later:** *"make it so that upon a reopening that page those that were held are also moved down in their own category (after prices, before all are sold/listed)"*. Three tiers now, and the order is theirs: the rows still wanting a price, then the ones already answered with a hold, then the ones this run can add nothing for.

**The timing is in the ask, and it is the part that matters.** The two sinks have different inputs. `bucket`, `at_cap` and `nothing_to_add` are the join's and cannot change while the screen is open, so sinking on them is free of D28. **A hold is this screen's own answer** (D49), and a row that dropped down the list the instant `H` was pressed would take the next row up to meet a finger already travelling to it — the exact motion D28 closed. So the group is read from `sunkHolds`, the set as it stood when `load` last ran, and it re-sorts on the next opening.

**Read the way a ROW reads it, which is why the snapshot walks the table rather than the two answer maps.** `targetOf` decides which map a row's answer lives in, so a stale `overrides` key for a `no_market_data` SKU draws nothing and must sink nothing. The group and the word `Holding` are then the same test, run once each.

**`"unlisted"` counts as held, and it is not an edge.** It is the answer a `no_market_data` row takes to say this card is not being listed, it draws `Holding` in the price column exactly as a reasoned hold does, and it keeps the card out of the same import file. A group of rows that will not list is the honest set; taking the reasoned half alone would leave the other half among the unanswered rows looking like work.

**ONE heading over all the holds, unlike the cap tier's one per sentence.** The reason is per SKU and is already drawn on the row as `withheld: <reason>` — the string D49 spent a line of chrome on precisely so it can be grepped from the screen to `decisions.json`. A heading per reason would scatter three rows across three headings to restate what each row already says.

**Where a row is both held and at the cap, the cap wins the placement.** The hold changes nothing about a SKU this run was never going to add a row for, so the deeper fact takes it; the `withheld` token still draws beside it, so the hold is not lost by being outranked. This is the same precedence the row's note line used to have, kept rather than reinvented.

**A row can outlive its group for one session, and that is the trade, taken with eyes open.** Release a hold and the row keeps its place under the heading until the next load, drawing a price field. The row tells the truth about itself and the heading says why the group is there; the alternative is the list moving under the release, which is the thing being bought. The browser case asserts both halves in one test — a case checking only the press passes against a screen that never sinks holds, and one checking only the reload passes against a screen that sinks them on the press.

---

---

## D79 — The reading goes on every row, because the operator answered D62's own measurement

**Built 2026-08-31, on the owner's ask: "Can we use this blank space in pricing between card and market to load and show the daily + weekly graphs that T loads?"**
This is not a reopening. D62 closed with the condition for its own amendment and named the
remedy in the shape it has been built: *"What would reopen this: the panel being opened on
every card… the honest answer is a batched route — `readings_for_rows` already exists in the
module and groups by productId — and a column on the row rather than a panel beside it. The
measurement is whether the operator presses `T` more often than they press `H`."* The
operator is the person who asked, and asking for the graphs on every row is that measurement
answered out loud.

**So what changed is the GRANULARITY OF THE PRESS AND NOT WHETHER THERE IS ONE, which is the half of D62 that survives untouched.**
That entry made the read a press because a follow-focus panel would fire one request per
arrow key at a free public mirror. Batching does not make those requests cheap —
**measured on `2026-08-31-box3-01`: 46 SKUs, ~92 requests, 37.7s cold and 0.15s warm**— it
makes them ONE DECISION instead of fifty. Nothing polls the route and no render fires it; a
`useEffect` on mount would spend that walk on every visit to `#/pricing` for readings nobody
asked for, which is D62's rudeness arriving by the other door.

### The blank space is not blank, and that is the request's one wrong premise

`--pricing-cols` gives the card `minmax(0, 1fr)` and every other column a fixed width. The card
is therefore not a wide column with room in it — it is
**whatever is left after the fixed ones**, so the gap the graphs were asked to fill is a
function of the window: generous at 1512px,
**zero at about 1150px, where the names are already truncating.** Drawn into that slack the
strip would be wide on a monitor, absent on a laptop, and would have taken the card name's
last readable characters on the way there.

**It is a real 168px column and it comes off the name deliberately, at every width.** Two
80px sparks with `--s2` between them. The cost is stated rather than hidden: at 1512px the
name keeps ~356px of the ~536px it had; at 1100px it drops to ~124px and truncates to
`Rengar, Trophy H…`. That is the trade, and it is the owner's to reverse by narrowing the
column or dropping the weekly spark.

**AND IT MOVED A HARD-CODED COLUMN INDEX THAT NOTHING WOULD HAVE CAUGHT.**
`.pricing-row-note` was `grid-column: 2 / -1` — the card, then everything after it.
Inserting a column at 2 put the note in the trend column's second row, which left
`.pricetrend` (spanning both rows, as
`.pricing-id` does) with nowhere to sit, so it was pushed into an implicit twelfth column off
the right edge and
**every figure slid one column left, on the rows carrying a note and not on the rows without.**
The caption stayed put, so it read as the reference block having come unaligned from its own
headings. The types check, `make lint` is clean, and `make design-check` has no floor over it. Found by
looking at the screen.

### A shape and a sign. No money on the row, ever

The row already carries four dollar columns and the field a listing price is typed into. A
fifth figure here would be a **reading** rather than a price, sitting inches from that
field, and the distance between reading it and copying it across is one keystroke. D8 makes
the export the pricing source and D62 refused to reopen it by name; `$16.33 avg sale` on
this row is that refusal being spent quietly rather than argued.

So the `vwap`, its bound, the liquidity and the within-bucket spread all stay on `T`'s panel,
where there is room to draw the anchor at size and the bound muted beneath it.
**The two drawings answer two different questions**— the panel says what one card is worth,
the strip says which of forty-six is moving — and that is why they are two routes with two
payloads rather than one route with a mode. `_history_spark` carries a range name, its span,
the momentum FRACTION and the bucket market prices; `_history_series` carries everything,
and sending it forty-six times would be ~19,000 numbers to draw one field of five.

### The caveats are stated once, above the list, and not forty-six times

D62's panel owes a reader three things and an 80px cell can carry none of them: that the
ranges OVERLAP and routinely point opposite ways, what span each covers, and that the wider
one can be the staler. They go in one line under the presets.
**That is honest because the spans are identical across every SKU of a run**— measured, all
46 on the run this was built against, both ranges — which is a fact about bucket boundaries
being global rather than per product, and the reason a per-row date would have been
forty-six copies of one string.

Direction stays a sign and never a color, which is D62's rule and binds harder on a list: a
colored percentage would be the loudest thing on the screen, over the least authoritative
thing on it.

### The rows this run can add nothing for are skipped, and stay reachable

The owner's second instruction: *"I don't need the prices for the rows that have none
left."*
`at_cap` is the field `cli/cmd_join.py` already writes and the same one those rows are grouped
under,
**so the filter and the grouping agree by construction rather than by two rules kept in step.**
14 of the 60 SKUs on that run, so 28 requests never made.

**They are not unreachable, and that is what makes the default safe.** `T` reads any one of
them, and an explicit `?sku=` overrides the filter — a caller naming a row has already
decided. The skip is a default over the run, never a rule about a SKU.

**And the count is on screen rather than implied.** A strip drawn over 46 of 60 rows with no
number beside it reads as fourteen failures; `46 read · 14 not asked` is what stops that.

### Chunked, sequential, and abandoned on a run change

Eight SKUs a request, walked in order — six waves instead of one 37-second blank, first
answer in about five seconds. **`Promise.all` over the chunks is refused**: it would finish
six times sooner by racing six sockets at a host that publishes no rate limit and asks
nothing of us, which is exactly the courtesy `pipeline/pricehistory.py` spends a constant
on. **The wall clock is not what is being optimised; the blank screen is.**

A generation counter abandons a walk in flight when the run changes or the button is pressed
again — without it a read started over run A keeps filling run B's column, one chunk at a
time, for the rest of the half-minute. And the strip is CLEARED on a run change where
`history` is deliberately kept: a reading is a fact about a CARD, but *which rows are still
open* is a fact about the run.

### Both directions, and a dead chunk is eight refusals rather than a stopped walk

Every asked SKU comes back in `skus` or in `refused` — the promise `readings_for_rows` makes
one layer down, kept across the two filters this route applies on top. The client spends it:
a SKU in neither map is written as a refusal naming that, because a SKU left on `reading…`
for the rest of the session is the silent drop `CLAUDE.md` forbids wearing a spinner. A
mirror having a bad minute costs the rows it was asked about and not the thirty behind them.

**What is not built, named rather than left to be discovered.** No sort by momentum — the
list order is `cli/cmd_join.py`'s and D28 forbids it moving under a finger. No `watch_above`
alarm, which is still the reading that would make one worth having (D49). No third range:
`quarter` and
`semiannual` are reachable and `DEFAULT_RANGES` is two, for the reason it has always been two.
No strip on `#/inventory` — D62's ruling that a reading belongs where a price is decided is
not disturbed by this.

**What would reopen this: the column being read on every visit.** It is a press because the
walk costs 37 seconds and ~92 requests at somebody else's mirror. If it turns out to be
pressed on arrival every single time, the honest answer is a cache with a life longer than
the hour
`HISTORY_TTL_SECONDS` gives it, argued on its own terms — not an effect that fires the walk
without being asked.

## Deferred — argued, not gated: nothing here is blocked, and none of it starts without a decision entry

**The heading read "do not build until all gates pass" UNTIL 2026-08-25, AND NO GATE HAS BEEN CURRENT SINCE 2026-08-23.** All three passed; `CLAUDE.md` and `docs/GATES.md` both say the gating system is retired and that nothing is blocked behind one. A list whose whole force came from a control that no longer exists reads as either binding or void, and neither is right. What actually holds these items back is `CLAUDE.md`'s standing rule — *scope is argued, not gated* — so the bar is a decision entry and an argument, not a gate that will never fire.

- PKMNVAULT and anything Supabase/eBay related, **except** the PKMNCODES track, whose manual eBay sales are allowed on the shared foundation.
- Riftbound / One Piece / any non-Pokémon TCG. The architecture already keeps the door open — the catalog join partitions by `Product Line` and builds one catalog per game (D25); only the export's Category filter and the finish enum are Pokémon-specific. **This line read "product-line-agnostic" until 2026-08-25 and D25 had already corrected it in as many words: measured, the join was product-line BLIND — the column was declared and read by nothing, so two exports concatenated would have cross-joined in silence. Blind is not agnostic**, and the two words point at opposite properties, which is why the stale one is replaced here rather than left to be read as agreement. Expansion later is config plus an enum, so no session redesigns for it early.
- Perceptual-hash identification layer (v2 accuracy cross-check).

---

## Someday — worth doing, blocking nothing

Distinct from Deferred above: those need an argument and a decision entry first. These are things that can be done any time, in any order, that no other work waits on. Nothing here belongs in a plan or a gate. If an item starts blocking something, it has stopped being a Someday item and needs a decision entry of its own.

- **Benchmark T1's eval images through TCGplayer Scan & Identify.** Hand-feed the same ~50 images and compare. Answers one question and only one: when Haiku scores below the floor, is the task hard or is the prompt weak? That reframes whether to keep tuning or move the bar. Manual, ~30 minutes, no integration code — see D2.
- **Measure what the set hint is actually worth.** D2 asserts identification is "better with it"; T1 can A/B it directly (`PKMNSCAN_T1_SET_HINT=1`). Watch both directions: a hint that raises accuracy but also raises *confidence on wrong answers* is a bad trade, because it converts review-queue taps into silently mislisted cards.
- **Send the number-corner crop on every card, not only on a retry.** `geometry/crop.py` exists, is tested by T6, and upscales the collector number to at least 600px — but the batch script only reaches for it when a first read comes back weak. T1's recorded misses are not weak reads. `051/197` for `031/197` and `271/167` for `211/167` are confident answers with the name right and the digits wrong, and a confidence threshold never fires on them.

  So: attach the crop alongside the downscaled card every time, and let the model read the number from pixels that were not thrown away. T1 measures it directly, the same A/B shape as the set-hint item above. Cost is roughly double the image tokens on a job D2 prices at $5–15 per 10k cards, so the downside is a few dollars and the upside is the number the gate rests on.

  Honest limit, and why this is Someday rather than a plan: it might do nothing. The crop-retry path was built on the assumption that enlarging the number helps, and that assumption has never been measured on its own — which is exactly what makes it worth an experiment rather than an edit.

- **Refresh prices against a scheduled pull, and keep the push out of it.** D65 made the export a scoped request, so fetching fresh prices on a schedule is now small — `fetch(Scope(...))` on a cron, storing a dated export, so a pricing decision is made against today's market rather than a file from three days ago.

  **The useful, safe half stops there: surface which SKUs have moved.** *These 23 have moved more than 10% since you listed them*, on `#/pricing`. The staleness gets answered and the decision stays with a person.

  **The push is a different thing and needs its own entry.** Three facts make it so, each checked rather than assumed. Nothing in the pipeline reprices anything — `join` picks a price at the moment it lists a card and `emit` writes it once, so "change the price of something already live" is a concept this product does not have rather than a feature it is missing. The import path is `initializeexportcsv`, `uploadexportcsv`, `finalizeexportcsv`, `rollbackexportcsv`, none of which appear anywhere in this repo; TCGplayer wrapping it in a transaction with a rollback is their own statement about how consequential it is. And `pipeline/pricing.py` has the arithmetic — match, undercut, markup, the $0.40 floor — but no opinion on *when* a live price should move, which is the part that decides whether a loop is useful or expensive.

  **If it is built, it takes D33's shape**: a free preflight showing exactly which prices would change and by how much, and a confirm that is not a default. An unattended loop that moves live marketplace prices is the one thing in this product that could lose money while nobody is looking.

**Three items left this list by being built, and they are struck here rather than deleted so that a later session reading an older copy does not reinstate them as open work.** Each one did what this list's own header says it must — *"if an item starts blocking something, it has stopped being a Someday item and needs a decision entry of its own"* — and each got one:

- ~~**Re-shoot a stored photo in place, long after capture.**~~ **Built 2026-08-23 — D26.** `POST /inventory/<box>/<index>/photo` replaces the bytes and rebuilds the sidecar with the record untouched and the allocator never involved, exactly as this item asked; the control is on the card detail, and D31 carries the rule that a merge may not drop it.
- ~~**A `removed` state for cards that leave inventory without a sale.**~~ **Built 2026-08-23 as `retired` — D26.** Renamed on the way in, and the rename is the finding: `removed` was already a history event name, so a state sharing it would have made months-old undo lines parse as states. Four reasons, reversible, and a sale now refuses a retired card.
- ~~**The owner can't see what a run produced without reading CLI output.**~~ **Built 2026-08-24 — D33.** `#/inventory` carries the run panel: every command's stdout verbatim, the import CSVs as downloads, and a money gate that cannot be pressed before the free preflight has answered. This item is quoted by name in `docs/GATES.md`'s "what the gate did not close", which is where it came from.

- **Back the photographs up to the NAS.** Asked and answered on 2026-08-30: the owner has a NAS and asked whether the photos and the store should live on it. **They should not, and the reasons are different for the two halves.**

  **The store would break, not merely slow down.** `store/files.py` rests on `fcntl.flock` (chosen, per its own docstring, *because* a process that dies holding one releases it — a kernel-local guarantee, and frequently a silent no-op over SMB) and on `os.replace`, whose own comment already states the constraint: *"only atomic within one filesystem."* `inventory.json` is 558 KB rewritten whole on every capture, at the feeder's 623 ms cadence, on primitives that do not hold. **D44 and D47 are this repo paying for that lesson twice already** — on iCloud, an in-place overwrite left Python's import machinery running old bytes while `read()` returned the new ones.

  **The photographs would be slow, and the slowness lands where it hurts.** 1.2 GB across 716 files. D36's realign hashes every photograph in a box on **every join** — 0.56 s locally, ~9 s over gigabit and worse over wifi, which is what this Mac is on. D19 budgets a capture round-trip under 250 ms, and a contended wifi hop mid-feeder-run is a silently missed card.

  **What IS worth doing is the backup, and it is a real gap.** Those photographs exist in exactly one place. Unlike D15's eval mirror — derived, re-downloadable, and which D47 records being rescued by iCloud version history in what that entry itself calls *"luck wearing the clothes of a backup"* — **a capture photo cannot be regenerated**: the card is back in a box. Lose the disk and D36's realign has nothing to bind to and D26's re-shoot has nothing to compare against. Either Time Machine to the NAS (no code at all) or a scheduled `rsync` of `inventory/` and `captures/`. If it is the second, it needs a line in `make status` saying when it last ran and whether it worked — a backup nobody checks is not a backup.

- **Cross-check the collector number against the local catalog** (needs D15). Not a replacement for the model's read — a second, independent derivation of the same fact, the same shape as D3 rung 3, where detected `finish` cross-checks capture metadata even when metadata already exists. The model returns `name`, `number`, `printed_total`; given a set hint, the catalog independently yields `(set, name) → number` and `(set) → printedTotal`. Agreement is confidence, disagreement is a review-queue reason.

  The two sources cover different failure modes, which is the whole argument for running both. T1's key misses (`051/197` for `031/197`, `271/167` for `211/167`) had the name right and the numerator misread — the catalog catches those. A name misread with the number right (`Rhydhorn` for `Rhyhorn`) disagrees from the other side — the model's digits catch that. Either source alone is blind to half of it.

  Honest limit, and the reason this is Someday rather than a plan: a cross-check converts misses into review-queue taps, not into correct answers. It buys safety, not a higher T1 number — the mirror image of the trade the set-hint item above warns about.

- **Keep a price series out of the exports runs already hold** (recorded 2026-08-29, from the owner asking whether the export carries last solds). The Filtered CSV is current-state only — sixteen columns, four of them prices, not one carrying a timestamp, a sale record or a sample size. `TCG Market Price` is the only column with sales behind it and it arrives as TCGplayer's own aggregate over recent sales, so *"what did the last three copies sell for"* is not answerable from it and is not recoverable from it by arithmetic. The `tcgplayer-csv` skill carries the schema half. **All of that is about the EXPORT and all of it still stands.**

  **What this entry got wrong, measured 2026-08-30 and corrected here.** It said, twice, that the data does not exist anywhere: *"It does not, and neither does anything else reachable from here"*, and **"TCGplayer publishes no price history at all, and that is the fact that decides the rest."** The second sentence is false and the first is false in its second half. `infinite-api.tcgplayer.com/price/history/<productId>/detailed?range=<r>` is **public** — no key, no cookie, no session, HTTP 200 to a bare `curl` — and it answers per-SKU daily and weekly sales history: quantity sold, transaction count, market price, and the low and high of the sales in each bucket.

  **The reasoning that produced the wrong sentence was sound and is kept.** It reasoned from the *latest-sales panel* on a product page, which really is UI-only and really would mean scraping the marketplace this project's listing path depends on, from the account that depends on it — a worse trade than the data is worth, and D2's rubric answers it before any code is written. That is a correct judgement about a different endpoint. What the entry did was generalise from the one surface it had looked at to the whole marketplace, and no amount of care about the first would have found the second.

  **The honest boundary is not where this entry drew it, and it is sharper.** The line is not *history exists / does not exist*; it is **aggregate versus fills**. A bucket says how many copies sold that day and the lowest and highest price among them. It does not say what any one copy sold for. So the sentence at the top of this entry survives verbatim and is now true of everything reachable rather than only of the CSV: *what did the last three copies sell for* is still not answerable, by this endpoint or any other one that does not need credentials. What IS answerable — and was not before — is what a card has been worth, how fast it moves, and which way it is going.

  **Recorded, not built — and the word is the point. `pipeline/pricehistory.py` exists as of 2026-08-30 with T7 coverage, and it is a LIBRARY: nothing calls it, no route serves it, no screen draws it.** `CLAUDE.md` says a wrap-up claiming BUILT for something unreachable is wrong rather than merely incomplete, so this entry does not claim it. What is genuinely built is a reader; what is genuinely done is this decision. Surfacing it needs a route, a client function in `app/src/server.ts` and a control on a screen, and that is the unfinished part of the same task rather than a follow-up. Per SKU the reader answers a volume-weighted VWAP on `marketPrice`, the interval that VWAP must lie inside, momentum, liquidity, units per transaction and within-bucket dispersion.

  **The two ranges overlap and the reader refuses to merge them.** `annual` is not the year before `month` — it is 357 days INCLUDING the same recent days at a coarser width, so concatenating them double-counts the recent window and skews any volume-weighted figure. They are kept separate and presented side by side. The wider range is also the staler one: weekly buckets are stamped at the start of their week, so `annual` ran six days behind `month` on the same card at the same moment.

  **The bound is a sanity check and never a result, which is the one way this could be misread into a wrong number.** With buckets rather than fills a true VWAP is not computable, only bounded. Measured on Moonfall (Unleashed 198/219) over `quarter`: a point estimate of **$16.33** inside a bound of **$12.54..$20.35** — 48% of the point estimate wide, or 62% of its own low end, which is why the module names both denominators instead of reporting one percentage. Anchor on the VWAP; a screen that ever draws the bound as a price and an error bar of comparable authority has read this backwards.

  **The join is local and the endpoint is keyed by productId, NOT BY SKU** (there is no SKU-keyed history route — probed, 404). `tcgcsv.com` mirrors TCGplayer's own catalog nightly, so the walk is `Product Line` cell -> categoryId, `Set Name` -> groupId, then (`Number`, `Product Name`) -> productId, all against a published mirror and none of it a scrape. The response then carries `skuId` on every result, so the last hop is EXACT: we ask about a product and take our own SKU out of the answer by its number. **Measured across all four committed exports: 3,588 distinct products, 100% resolved, zero ambiguous, zero missed**, with all 19 set names matching their group names exactly.

  **The same mirror serves current prices, and they are product-level rather than SKU-level — which is what keeps D8 shut.** `/tcgplayer/<cat>/<group>/prices` answers low/mid/high/market and a direct low per product per PRINTING: 445 rows over 321 products for Unleashed, `subTypeName` being `Normal` or `Foil` and never a condition. Vilemaw is five export rows by condition against one row there, so it can only ever speak for the Near Mint row.

  **That it is the Near Mint row was measured rather than assumed**: across 387 multi-condition Unleashed products this figure is nearest the export's Near Mint row **338 times, 87%**, and the 49 that are not have a median gap of **$0.04** between their two closest condition rows — 41 of the 49 under $0.25 — so those are the instrument failing to discriminate rather than the inference failing. It remains an inference the payload does not state, and it may not be used to price a played copy. It carries no `TCGplayer Id` and no `Total Quantity` — the SKU D11's import matches on and the quantity D7's cap is measured against — so **it supplements an export and can never replace one**, and the field sets are not a mirror either: `midPrice` and `highPrice` have no export column, and `TCG Low Price With Shipping` has no field there.

  **What it actually buys is RECENCY, not a new dimension**, and that is worth saying flatly because "supplements the export" reads like the opposite: every figure is already a column the operator has, offered as of now rather than as of the last download.

  **AND `number_index_key` IS REUSED ON BOTH SIDES RATHER THAN REIMPLEMENTED**, which is the same rule that stopped `pipeline/join.py`'s silent zero-join. The name is consulted only as a tiebreak and then as a last resort, and the measurement says it is doing nothing riskier than that: of the 3,588 products, 355 resolve by name and **all 355 carry a blank `Number` cell** — sealed product, code cards and DON!! cards, which print no collector number at all. Not one row with a number in it has ever fallen through to the name index. That is the measurement to re-run first if anything here is widened.

  **What was already true and is unchanged.** D33 makes an app-driven run keep the exact export bytes it joined against, so keying `TCG Market Price` by `TCGplayer Id` across run directories is still a price series that grows every run and calls nothing. It is still the cheapest thing here and it still cannot cover the backfill. `tcgcsv.com`'s daily market/low/mid/high archive back to 2024-02-08 is still the candidate for that, and this build uses that mirror for the CATALOG only — it reads no price out of it.

  **eBay sold listings are a real source and the wrong one.** Officially reachable through the Marketplace Insights API rather than by scraping, but eBay is on the Deferred list above, and an eBay sold price is shipping-inclusive on a different market — it would mislead a TCGplayer listing price rather than inform it.

  **D8 is not reopened and the reader must not reopen it.** That entry names the TCGplayer export as the pricing source and no external pricing API, and **nothing in `pipeline/pricehistory.py` prices anything**: it computes no listing price, writes no `TCG Marketplace Price`, and is reached by no command that emits a row. It is a reading taken NEXT TO the export rather than instead of it. The day something wants a listing price to depend on a trend, that is a change to D8, argued on its own terms — and it is a change this module makes cheaper to argue rather than one it has quietly made.

  **What it is worth**: D49's `bullish` withhold and its `watch_above` threshold are the only things in the product that want a trend, and they have had none — a hold is set against the operator's memory of what a card used to cost. The verification case is Vilemaw (Unleashed 060/219, sku 9189317, three copies in box 3). **Read on 2026-08-30**, and dated because every figure in it moves: export market $23.14 against a live $23.63 at daily resolution ($23.73 read over `quarter`, whose buckets are three days wide), **1,763 copies sold in the quarter**, and a month and a year pointing opposite ways — up 71% over the month, down 34% over the year. Neither number was available to this product the day before, and no aggregate of them is a last sold.

  **What would reopen this: the endpoint closing.** It is undocumented and unversioned, and a public thing that nobody promised can stop being public without notice. The reader refuses by name rather than guessing when it does, and the failure is a missing reading rather than a wrong price — which is the property that made it safe to build against at all.

- **A realised-price series is obtainable, from the OrderWand extension's sales export** (recorded 2026-08-30). OrderWand is a buyer-side order-history browser extension that also exports seller sales, as a CSV, on demand. **No path is named here on purpose: the export is a snapshot the operator regenerates, not an artifact this repo keeps.** It carries buyer names and so belongs nowhere in the tree — not even beside `inventory/` and `runs/`, which are gitignored for being real and local rather than for being private. Every row carries a price **and** a `Vendor Product Id`, and that id is a TCGplayer `productId`, which is the key `infinite-api` already takes. So an export joins to the series in the entry above with no lookup at all, and answers the one question that series cannot: not what the market did, but what this seller actually got for it.

  **One export, taken 2026-08-30, held 715 sale lines across 543 orders spanning 2026-05-05 to 2026-08-30, $56,194 of realised sales.** Every figure below is measured on that file and is evidence about it rather than a claim about the next one.

  **What it cannot do, recorded so that nobody re-investigates it for the wrong reason.** It carries no SKU. All 301 distinct `Vendor Product Id` values are six digits; Moonfall's productId `684527` is present and its SKU `9191486` is not; the overlap with the 102 SKUs the store holds is **zero**. Nor can a SKU be derived from it, because `Condition` reads `unknown` on 511 of the 715 rows and `Product Type` on all 715, and a SKU is a product plus a printing plus a condition. It is also an export of settled history rather than a feed of open orders, so it cannot serve the order flow whatever else it does.

  **Regenerating one needs the extension still installed**, which is the only reason to keep it: the value is the file rather than the ongoing access, and the extension declares personally identifiable and financial scope under no verified publisher. If it goes, the last export taken is the only copy and should be kept somewhere deliberate.

  **Honest limit, and why this is Someday rather than a plan:** it measures the past and moves no price by itself. Realised-versus-market is a diagnostic — it says whether this seller has been leaving money on the table — and converting that into a listing rule is a separate argument that would need an entry of its own. The file also ages: it is a snapshot rather than a subscription, and refreshing it is a manual export.
---

Unsorted scanning is **not** deferred: it works today via the optional hints, with more review-queue traffic. Just do not optimize for it ahead of work that has a decision entry. (This read "before Gate C" until 2026-08-25; Gate C passed 2026-08-22.)

---

## v1 bugs — do not reintroduce

| # | Bug | Guard |
|---|-----|-------|
| 1 | Variant mispricing — blindly took `holofoil \|\| reverseHolofoil \|\| normal` | Harness test 4 (variant ladder) |
| 2 | Naive `split(",")` CSV parsing | Harness test 2 + lint rule |
| 3 | `facingMode: "environment"` broke desktop camera selection | Device picker; lint rule |
| 4 | Web Audio contexts created per-sound, never closed | Code review checklist |
| 5 | CSV import matched by box+position, silently skipped identified cards, reported nothing for unmatched rows | Harness test 3 (bidirectional reporting) |

## D80 — A section with no reader is deleted or given one, the build order stops pretending to be a sequence, and the map gets a view a person can use

**The map was never stale in the part anybody checked, and that is the finding.** `docs/map.py` took 75 commits on 2026-08-30 alone. Measured properly — `git blame` on the map's own lines for each of its 155 module entries, against that file's last commit — **142 of 155 entries were written at or after the file they describe last moved**, worst gap 17 days. The `repo map` row was green throughout, at 166 entries. No other prose in this repo is maintained that well.

**What had gone wrong was everything the map says about ITSELF, and it correlates exactly with having no reader.**

| section | reader before this entry | state |
|---|---|---|
| `COMPONENTS` | the audit, the hook, `make status` | current, 2,400 lines of it |
| `BUILD_ORDER` | `make status` | every row accurate; the SHAPE was lying — see below |
| `GATES` | the audit, reconciled against `docs/GATES.md` | correct |
| `TRACKS` | **nothing** | wrong twice, for three weeks |

`TRACKS` said `C1-C7` after `docs/CODES-DECISIONS.md` had reached C11, and said the codes track's delivery automation was **"gated on singles Gate B"** — a gate that passed 2026-08-22, in a gating system retired outright on 2026-08-23. Both false for over three weeks in the file whose entire argument, D17, is that it is audited exactly as hard as it is trusted.

**A section with no consumer is worse than a section that is wrong.** Wrong-with-a-reader is found the first time somebody runs the reader. Wrong-with-no-reader is a claim the repo makes about itself that has no way of ever being contradicted, and it decays silently while looking exactly like the sections that work. So the rule is: **give it a job or delete it**, and `make docs-audit`'s `map sections` row fails the commit that adds a top-level name nothing reads.

**`TRACKS` was given a job rather than deleted, because it turned out to answer a real question nobody was being asked.** `scripts/decision-context.py` resolves a file to its decisions through `COMPONENTS` only, so a session editing `codes/` was shown the D entries the rig shares and **was never told that C1-C11 and a second rules file exist at all** — D14's two-tracks-one-rig arriving as a surprise at the worst moment. The track now carries an `owns` prefix, the hook routes by it, and `scripts/status.py` declares `TRACKS` in `SOURCES` so the `status sources` row fails the commit that deletes it.

**The build order is a backlog now, and it is not renumbered to pretend otherwise.** Step 15 is the last step anyone added; D34 through D77 landed after it and not one is a step. That is not the map falling behind — work is proposed and argued in this file, and the numbered list is what is left of an ordering that already happened. Step 9 is the exception and is genuinely open: nothing has vendored the catalog. So steps 1-15 stay exactly as they are, under the rule `docs/GATES.md` applies to its own measurements — **what happened is not edited to match a later tree** — and the header says which of the two it is. `build order mirror` checks the step NUMBERS against GATES.md's numbered list and deliberately not the titles or statuses, which the two files word differently on purpose.

**The map had no human view, and that is why nobody could tell.** 2,700 lines and ~56,000 tokens — a third of what D60 dropped the `@` over — so the docstring's promise that one Read answers the question had quietly become a promise to spend a fifth of a context window. `make status` lifted three lines of it and nothing rendered the rest. **A file that can only be read whole is read by nobody and edited by everybody**, which is the mechanism behind every row of the table above. `make map` renders it: the shape, one package, one module, everything a decision governs, and `--stale`.

**`--stale` reports what no audit row can, and is deliberately not one.** It is the blame measurement above, run on demand. A note written to outlive a refactor is not a defect, so it ranks suspicion and never fails — the same reasoning that keeps `views exposure` advisory, one step further out.

**The docstring's own consumer list is checked, because it was wrong in the way that matters most.** It said "three consumers" and omitted `scripts/status.py` — **the only one a person runs**. A reader asking how to look at this file was told, by the file, that there was no way to.

**The build order was the second half of the same disease, and the harder half, because every individual row in it was true.** It was one numbered list with a `status` field, and a numbered list renders one way: `make status` led with **"Build step 9 of 15"**. At that moment 13, 14 and 15 were done, step 9 had been deferred by choice for a week while the owner shipped pricing, orders and the code-card track, and D34 through D79 had landed with no step at all. **No correction to any row fixes that**, which is why the first pass at this entry left the list alone and argued that it was a backlog — a defense of the shape, offered instead of a repair.

**So `status` is deleted and the list a step is in IS its status.** `SHIPPED` is ordered by the date the work landed; `OPEN` is **not ordered and carries no `next`**. Dropping `next` is the point rather than a side effect: the rule "exactly one step is next" required *something* to hold the flag, so step 9 held it for nine days across two rounds of re-sequencing while the work went elsewhere. A rule that forces an answer will get a false one when there is no true one to give. Ranking two open items is the owner's call, `make status` has no standing to make it, and its `DO THIS NEXT` heading made it anyway.

**`n` is a stable id and is never renumbered, and this is not tidiness.** 218 references to `step <n>` live in this tree — CLAUDE.md, README.md, `.claude/settings.json`, six specs, this file, harness code and Playwright specs — and **74 of them say `step 7`**. A renumber leaves every one pointing at a real step that is not the one meant, and **nothing could detect it, because a stale number still resolves**: D72's citation drift, at eight times the scale of the incident that earned D72 its own audit row. So the ids run out of order in `SHIPPED` (11 landed before 4) and there is a hole where 12 was, and both are correct.

**Steps 16 to 19 were added for work that had already landed** — hand pricing, the order pipeline, the code-card track, and the rig's guards — and each carries what it did NOT do in the same row, because that is the half a shipped-list is tempted to drop. **Step 12 was culled, the only row ever removed from this list.** It read *"Only then: scale, polish, deferred list"*, named no deliverable, and its *"only then"* pointed at the gating system retired on 2026-08-23; it then spent a week `blocked` on step 9, a dependency invented on its behalf so it would not have to claim a blocker that no longer existed.

**Culling is affordable now, and it was not before.** `docs/GATES.md` carried a paragraph explaining that steps were appended rather than inserted because renumbering "would have to land in four files at once" and nothing watched them. `build order mirror` reconciles the ids in both files, per list, in both directions — so adding, moving or removing a step is a two-file edit a machine refuses to let you do halfway.

## D81 — The presence gate is a distance from this session's own baseline, and the stillness thresholds are multiples of what this session measures

**Built 2026-08-31, after the owner's fourth motion trace and a direct question: whether the capture trigger was ever the dynamic thing it was described as.**
The honest answer was no, in the half that was costing cards, and the traces settle it
rather than anybody's recollection. `scripts/score-trace.py` is the pass; run it on the four
saved traces and it prints the same numbers this entry argues from.

### What was actually wrong, and it was a mistake of KIND rather than of tuning

The trigger has two halves and only one of them was ever dynamic. Motion detection is a
frame-to-frame difference, which is inherently relative and cancels the light level — that
half has found the cards in every session ever traced.
**The card-PRESENT gate was a brightness compared against the constant 90**, and no constant
can do that job:

| scene | rig / session | bright quantile |
|---|---|---|
| **empty stand** | reference rig, 2026-08-23 | **57** |
| card | under-lit rig, 2026-08-29 21:34 | **61**–134 |
| card | 2026-09-01 | 77–171 |
| card | reference rig, 2026-08-23 | 196–244 |

**An empty stand at 57 and a real card at 61.** Four luma levels apart, on different days,
with the floor at 90 sitting *inside* the card population of three of the four sessions. The
bill:
**20 of 20 cards refused on 2026-08-29 21:34, 13 of 15 on 21:38, 5 of 24 on 2026-09-01 — 38 real cards called an empty stand, silently**,
against exactly ONE correct
refusal in the whole corpus (the genuinely empty stand at arm time on 2026-08-23). Every
frame was rendered and looked at; there is a card in all 38.

**The 2026-08-29 quantile fix was the same mistake one layer in.** It changed which
brightness statistic the constant was compared against — mean to p90 — and the constant was
never the right shape of thing to compare a brightness against. It also derived the "empty
stand" numbers in its own table from frames that were photographs of real cards, because a
refusal was read as evidence of what was on the stand.
**`scripts/score-trace.py contact` exists so that cannot happen a third time**: it draws
every verdict's frame as a labelled
contact sheet, and the only thing that settles what a frame contains is looking at it.

### The ruling: presence is distance from a baseline this session took

**A settled frame is a card when it differs from the watch region as it stood when armed**,
by more than `presenceK` × this session's own typical still-frame
difference, floored at `presenceMin`. Scored over the same four traces:

- an empty stand sits **1.10–1.38** from its own baseline
- every card of every session sits **17.4–167.4**

**A 43× gap where brightness gave 1.07×.** Every value of the floor from 6 to 10 gives
byte-identical verdicts on all five traces, which is what a real gap between two populations
looks like; 8.0 is the middle of it, and is set by illumination DRIFT rather than by noise —
a static scene walks up to 7.94 from a baseline seconds old, measured.

**What this deliberately gives up.** A card already at the lens when the trigger is armed
becomes the baseline, and is refused rather than captured. That behavior was real and is
now gone. **It is forced rather than chosen**: the old machine captured it only because the
card was bright and 90 happened to sit under it — the exact mechanism the table above
convicts — and nothing in a single frame separates "the stand as it normally looks" from
"the stand with a card on it" without a reference. At arm time the reference is what is
being established. The cost is one photograph at the top of a run; the old cost was twenty
mid-run.

**The failure direction is inverted on purpose, which is the point of the whole entry.** A
wrong baseline now causes EXTRA fires — visible in the strip, undone with `U` — where the
old gate caused silent refusals. And a run of refusals is no longer a counter climbing
beside six other counters: `noCardRun` counts them consecutively and the capture screen
renders three in a row as the sentence it means, naming the cause and the remedy. The remedy
is a `Re-baseline` control on the HUD, a button rather than a letter because it is performed
after clearing the stand with a hand already off the keyboard, and because the letter it
would want is the box field's.

### The stillness thresholds go the same way, and the repo's own history is the receipt

**The 2026-08-23 retune (`tLo` 3.0 → 4.5) was a person at a rig discovering that the live preview's noise floor is eleven times the stored JPEGs' one**
— after 14 of 86 cards had
gone past the lens without ever reaching a verdict. That is a measurement the machine can
take in eight seconds. `tLo` and `tHi` are now `stillK` and `moveK` times the median
frame-to-frame difference of the last 8 s of frames the machine already called still.

| trace | presentations | live constants | adaptive |
|---|---|---|---|
| 2026-08-23 02:49 (`tLo` 3.0) | 85 | 72 | **86** |
| 2026-08-23 03:09 (the tuned 85/85 run) | 85 | 86 | 86 |
| 2026-08-29 21:34 | 19 | 20 | 20 |
| 2026-08-29 21:38 | 14 | 15 | 15 |
| 2026-09-01 | 25 | 24 | 24 |

**Met or beaten on every trace**, including the one whose silent misses cost a rig trip to
diagnose. `stillK` was chosen from a sweep over all five traces at once rather than tuned on
one: 2.0 sits in the middle of a plateau (2.0–2.5 all meet live everywhere) instead of on
the edge of a peak, which is the failure mode of the 2026-08-23 retune repeated with better
manners.
**The seed reproduces Gate C's hand-tuned pair to the last digit — 4.50 and 8.00, so the machine boots on the constants the 85/85 run was confirmed on and adapts away from them.**
Nothing about that run is being re-litigated; it is being made portable to a rig
that is not that one.

**Only frames the machine already calls still feed the estimate**, and that restriction is
the direct answer to `motion.ts`'s own former objection that "an EMA floor that learns
during slow motion is a way to go blind". A hand resting half in frame, a jammed feeder, a
card creeping: all sit above `tLo`, never enter the window, and cannot redefine what
stillness is. The one thing this cannot recover from is a session whose noise is entirely
above the seeded 4.5 — and that failure is loud rather than silent: not one capture is taken
and the HUD sits in `moving`, which is the opposite of the failure being fixed.

### What did NOT change, and why each one is a decision rather than an oversight

**`tNovel` stays an absolute 4.0.** Across all five traces and 217 verdicts, the
`suppressed:unchanged` count is **zero** — there is no measurement to derive a multiple
from. And scaling it to session noise would push it DOWN on a quiet rig, making suppression
more likely, which is the wrong direction: a false pass is a duplicate `U` fixes, a false
suppression is a silent loss. It stays until a trace convicts it.

**`refractoryMs` and `maxMoveMs` stay absolute** because they are times, not light levels;
nothing about them is a constant compared against a measurement.

**The HUD lost `luma` and gained `dbase`, `floor`, `tlo`, `thi` and `typ`.** Every number on
that row is now one the machine decides on. The row carried `luma` for two rig sessions
while the gate read a different statistic, which is how a rig gets debugged against the
wrong number; the bright quantile survives in the trace, as evidence about lighting, and
gates nothing. **The trace is version 2** — a v1 row is `[t, d, luma]` and a v2 row is
`[t, d, dBase, luma]`, and a scorer that read the third column as brightness would read a v2
trace as a rig with no light in it.

**What would reopen this:** a trace where a card is genuinely indistinguishable from the
baseline — a white card on a white stand under flat light, where distance is as blind as
brightness was. The answer then is not a third constant but a second signal (edges, or the
stand's own fixed landmarks), and it should arrive with a trace attached like this one did.

## D82 — Ruff is adopted on the slice this session measured, not on what it enables by default

**Adopted 2026-09-01, closing the question `make lint` left open since it was narrowed to JavaScript.**
Python has no linter here. `docs/specs/audit-retirement.md` §9 already set the format for
answering that kind of question — run the tool on this repo, read the findings, then decide
— and this entry is that format applied to the one row that section left as "unmade."

**Zero-config `ruff check .` found 2,131 things on this tree, and 79% of it was one wrong assumption.**
1,051 `UP006`, 479 `UP045` and 148 `UP035` findings — 1,678 of 2,131 — are
pyupgrade rewriting `Dict`/`List`/`Optional[X]` to PEP 585/604 syntax. `requirements.txt`'s
zxing-cpp comment already says why that matters: this repo runs Python 3.9.6, pinned,
load-bearing. `X | None` outside a deferred annotation is a runtime `TypeError` on 3.9, and
ruff's own zero-config default assumes a newer interpreter — it marked most of those
rewrites "safe" until told otherwise. Telling it `target-version = "py39"` flips the split:
of 1,965 pyupgrade-family findings, safe-fixable drops from 1,798 to 264 and unsafe rises
from 169 to 1,701 — ruff itself stops trusting the rewrite once it knows the truth. The
codebase already defends itself here (57 of 63 files under the audited packages carry
`from __future__ import annotations`; the 6 that do not are empty `__init__.py` stubs), but
a bare `ruff check .` followed by `--fix` would have spent that discipline for nothing.

**The measured signal, once the version is told the truth, is pyflakes plus a validated slice of bugbear and flake8-simplify.**
Not ruff's ~900 default-enabled rules. Pyflakes and
basic pycodestyle (`E4`, `E7`, `E9`, `F`) came back with 29 findings, every one read by
hand: dead imports, extraneous `f""` prefixes, unused test-local variables, two ambiguous
`l` names, one `lambda`-assignment, and two `Optional`/`Tuple` names used in an annotation
without being imported — shielded from a live `NameError` by the same deferred-annotations
discipline above, but real hygiene gaps. Zero were false positives; zero were live bugs.
Bugbear plus flake8-simplify (`B`, `SIM`) came back with 39, and this is where the tool's
blind spots showed up before they shipped:

- `SIM115` flagged every `open()` this repo deliberately keeps past its own function's
  return — the `flock` handle a lock holds open for the caller's whole critical section
  (`store/files.py`), and the log handle handed to a detached `subprocess.Popen` that
  outlives the spawning function (`scripts/serve.py`, twice). The rule has no way to see
  either invariant; both are now a per-line `# noqa: SIM115` naming it.
- `B023` flagged a closure over a loop variable in a concurrency test
  (`harness/tests/t7_store_and_seams.py`) where the closure is started and joined within
  the same iteration, before the next one rebinds what it captured — bugbear's documented
  blind spot for a closure consumed synchronously rather than escaping the loop.
- `SIM118` is the one that actually broke something. It flagged six `for game in
  games.keys()` calls in `cli/resolve.py` as the dict idiom `key in dict.keys()`, and
  `games` there is the `pipeline.games` MODULE, not a dict — `keys()` is a real function
  it exports, unrelated to `dict.keys`. Applying the suggested rewrite (`for game in
  games`) parses fine and fails at runtime: `TypeError: 'module' object is not iterable`,
  three tests deep into `make harness` (T3, T4, T7), through `cli/cmd_join.py` ->
  `cli/resolve.py:games_claimed`. Ruff has no type information here — it pattern-matches
  the syntax `x in y.keys()` regardless of what `y` actually is. Caught by running the
  harness before calling the fix done, not by anything ruff itself could have said;
  reverted, and the six sites carry `# noqa: SIM118` naming the module.

**The ruling: `ruff.toml` pins `target-version = "py39"` and selects exactly `E4`, `E7`, `E9`, `F`, `B`, `SIM`.**
Never ruff's own defaults, and never `--fix` on this codebase without a
harness run after. `make lint` runs it alongside eslint, gated by the same shape of guard
`NPM_GUARD` already used (`RUFF_GUARD`, `requirements.txt`), so a missing dependency fails
loudly rather than letting `make check` go green having checked nothing. `--fix` is not
wired anywhere, matching D18: nothing that writes may run on the path that decides whether
a commit proceeds, and this repo has now measured, on its own tree, that an automated
rewrite here is not a decision to make blind.

**What this does not cover.** The other ~890 rule categories ruff enables by default —
everything outside pyflakes, bugbear and flake8-simplify — are unmeasured against this
repo and stay off. Widening the selection is a repeat of this same process: run it, read
every finding by hand, and record what is real before it gates anything.

---

## D83 — A card leaves a box through a third door: moved, not sold or retired

**Built 2026-09-01, on the owner's want to unbind runs from boxes and rip whole vats of cards between them — "I feel like I'm in a prison of my own making."**
A card's position has always been `(box, index)`, baked into the store's dict key, its
photo's filename, its sidecar, its section boundaries, its queue entries and its listing
holds — and no primitive anywhere moved one. This entry is the primitive.

**A move is the same kind of event as a sale or a retirement, not the same kind of event as `do_remove_card`'s mid-box delete.**
Two shapes were on the table. One generalised the delete-with-shift: cascade every higher
card in the source box down one index, the way a delete already does. The other left the
vacated position a permanent tombstone and recorded the card fresh at a newly allocated
index elsewhere — D26's `retired` pattern, extended to a third destination instead of an
exit. The cascade shape lost, for a reason sharper than taste: D58 (2026-08-30, two days
before this entry) already re-argued and rejected moving the stored index for exactly this
class of change, building `pipeline/join.py:Position` specifically so stored indices can
stay put forever while rendered ranks close up over gaps. Reopening that argument for moves
would not just fail to reuse D58's machinery — it would actively refight it. And the cascade
shape has a second, harder failure: it inherits `do_remove_card`'s `renumber_blocked`
refusal, which blocks a shift across any sold, retired or listing-held card above the
target. A box that has been sold through even partway would refuse to give up almost
anything through that door. The tombstone shape refuses none of that, because nothing else
in the box moves.

**`MOVED` joins `master.TERMINAL_STATES`, and that membership is where the payoff is.**
`pipeline/join.py`'s occupancy rendering, `_Places`, `copies_on_hand` and every other reader
already key off that tuple to decide what still occupies a box — so a moved card's gap
closes up on screen for free, with zero changes to any of them. This is the same kind of
"add a state, inherit the machinery" move D26 made for `retired`, applied a second time.

**The tombstone clears `sku`, `condition`, `capture_id` and `photo`; the transplant keeps them.**
This is the sharpest correctness requirement in the whole change, not decoration.
`copies_not_sold` (D59's per-SKU shelf cap) and `positions_for_sku` both filter on `sku`
alone, with no state exclusion — a tombstone that kept its SKU would be counted alongside
its own transplant forever, double-billing every cap and every copies-of-this-SKU list.
`capture_id` moves for the reason `card_by_capture_id` exists at all: two cards sharing one
id raises `DuplicateCaptureId`. Descriptive fields — name, number, game, confidence and the
rest — stay on the tombstone, exactly as `retire()` leaves them, so a person looking at the
old slot's history still sees what card used to be there.

**No listing-hold guard, unlike `do_remove_card`'s `card_listed` refusal.**
D7 already treats a SKU's backing copies as fungible and position-independent — which
physical copy backs a stage is deliberately unrecorded — so a card carrying an active
listing hold is free to change boxes. The hold travels with the transplant's `sku`
untouched, and nothing about `_release_plan`/`_listing_hold` reads a card's box in the
first place.

**Undo is not a separate operation, control, or result shape.**
A transplant is not itself terminal — it is a normal record in whatever state it was in
before the move — so moving it back is calling the same primitive again, in the other
direction. It lands at a *fresh* index in the original box; the first tombstoned key is
never reclaimed, the same permanent-gap behavior every other terminal state already has. No
`undo_move` route exists and none is needed.

**A card that has already left through this door refuses to leave again.**
`card_moved` joins `card_sold` and `card_retired` at every route a departed card's
target-state check already guarded: `do_remove_card`, `do_delete_box`'s blocker naming,
`do_mark_sold`, `do_retire`, and `do_reshoot`. `store/master.py:Inventory.move_card` raises
the generic `CardDeparted`/`CardNotFound` as a backstop for any caller that reaches it
without going through a route's own richer check — the same belt-and-braces relationship
`BoxClosed` already has with `allocate_capture`.

**`_state_before_sale`/`_state_before_retirement` needed a third guard, not just the two they already had.**
Both scan `history.jsonl` backwards for the last event naming a state, filtered against
`master.STATES` — and `MOVED` becoming a member of that tuple means a hand-edited or
corrupted history carrying a `moved` line directly under a `sold` or `retired` one would,
without a guard, be handed back as a state to restore *to*. That is worse than the
`retired`-under-`sold` hazard those functions already refuse: `set_state` accepts `moved`
without complaint, since it is a plain state, but `Inventory.move_card` is the *only*
correct way to reach it and never calls `set_state` — so a card restored to `moved` this
way would carry no `moved_to`, no transplant, and no tombstone shape at all. Both functions
refuse with `None` on a `moved` line, mirroring their existing `retired`/`sold` refusals
exactly.

**The batched primitive, `Inventory.move_cards`, is one call inside one lock, and order is the caller's.**
Each card handed in ascending source-index order consumes the destination's next
`next_index()` in turn, so a ticked selection or a section lands contiguously at the
destination in the same relative order it left in — no separate bookkeeping for it. A whole
box moved this way (`indices: null`) *is* a merge, from the caller's side; there is no
separate merge route, and none is needed.

**`_box_row` gained a `moved` count, beside `sold` and `retired`.**
Same reason those two exist at all: so the delete panel can name which of
`box_not_empty_of_commitments`'s grounds is holding a box open before anything is pressed.
A box emptied by moving every card out of it (the merge case) is left holding only
tombstones — departure records exactly like sold or retired ones — and stays undeletable
through `do_delete_box`'s existing gate until each is accounted for. This is a real, named
cost of a merge: the source box cannot be reclaimed for reuse afterward. Surfaced on the
confirmation screen rather than discovered at a later delete attempt.

**Named risk, not fixed here: the file move happens after the store call, not before.**
`do_remove_card`'s "files first" ordering works because its destination indices are
deterministic (`at - 1`) before any record is touched. A move's destination index is not
knowable until `Inventory.move_card` allocates it, so the photo rename necessarily comes
after. A crash between a successful rename and this request's commit leaves a photo at the
new path while `inventory.json` still names the old one; recovery in that narrow window is
manual. A second, related risk: `cli/resolve.py:realign` reads photo bytes off disk with no
lock at all (a free, re-runnable CLI step, by design), and a move's cross-directory rename
can race it. Neither is fixed in this entry — the accepted mitigation is not running a move
concurrently with a `join --realign`, named rather than engineered around, in the company of
`_sale_origin`'s own unlocked read.

**What this entry BUILDS:** `MOVED`/`Card.moved_to`/`Box.section_names` in
`store/master.py`; `Inventory.move_card`/`move_cards`; `do_move_card`
(`POST /inventory/<box>/<index>/move`) and `do_move_cards`
(`POST /inventory/<box>/move`, `indices: null` serving a whole-box move/merge); the six
`MOVED` arms across `do_remove_card`, `do_delete_box`, `do_mark_sold`, `do_retire`,
`do_reshoot` and the two `_state_before_*` guards; the `moved` count on `_box_row`; the
client functions `moveCard`/`moveCards` in `app/src/server.ts`; and a reachable control —
"Move to box" — beside Set Claims in `BoxOps.tsx`, gated on the ticked selection or the
box's on-hand count exactly as Set Claims is, taking a typed destination box number.

**What this entry does NOT build, named rather than left silent:** a searchable box picker
(the control takes a typed number, not the richer name-search field the capture screen
uses); a dedicated section-move affordance that reads a section's own name and carries it to
a fresh divider at the destination (`Box.section_names` exists on the record but has no
write path yet — sections move as plain index lists, unnamed); a dedicated split-box route
(reachable today as create-a-box-then-move-into-it, two requests rather than one); and D48's
reopening — an operator-chosen `combine` flag letting one identification run span several
boxes. All four are compositions of, or thin additions beside, what this entry built rather
than architectural gaps in it, and D48 in particular is unchanged and ungoverned by this
entry: the cart still spawns one run per box, and an operator who wants one ruling across
boxes has no way to ask for it yet.

**What would reopen this:** a move that needs to cross a filesystem boundary (today
`captures/cards/` is one tree and `os.replace` is atomic across it; a store layout that
splits boxes across mounts breaks that assumption); a demonstrated need for the crash-window
risk above to be closed rather than merely named; or the owner asking for the four
not-built pieces above, in which case each is its own small entry rather than a reopening of
this one.
## D84 — A settle is a count over a window, the stall clock is cleared by a settle, and the presence floor is sized to a hand

**Built 2026-09-01, from three traces the owner recorded after D81 and handed back with one question: whether those were flawless runs.**
They were not, and neither defect was visible from the rig — one put junk in the box and the
other lost cards in silence. `scripts/score-trace.py` is the pass; run `summary` and
`presence` over the three 21:xx traces in `harness/traces/` and it prints what this entry
argues from.

### What the three sessions actually cost

93 seconds of feeding, 69 fires, and every fire landed on disk — the trigger's plumbing was
never in question:

| | cards fed | good captures | photographs of the bare stand | **fed and never photographed** |
|---|---|---|---|---|
| 21:10 | 47 | 45 | 1 | **2** |
| 21:14 | 13 | 12 | 1 | **1** |
| 21:16 | 11 | 10 | 0 | **1** |

**The four losses were established by looking, not by inference**,
which is D81's own standing instruction. Every one of the 69 JPEGs was downsampled to the trace's 38×28 watch
region and matched against the recorded frames: a true match scores MAD 13–19, and the four
orphan scenes score 23.7–30.2 against their nearest photograph. They are in no file. The two
junk fires were opened and read — the bare stand, at the top of a box.

**Every defect sits in the first two seconds after arming.** After that the cadence is
metronomic: 43 consecutive fires in the longest session with no gap over 1.0 s.

### Ruling 1 — a settle is `stillFrames` of the last `stillWindow`, not a consecutive run

A consecutive run is defeated absolutely by a two-frame alternation, and the alternation is
measured rather than feared. A card motionless for 500 ms at the head of the 21:10 session,
against a tLo of 4.18, every frame:

    2.71  5.40  2.63  5.54  2.83  5.14  3.03  4.80  3.64  4.91

Five separate runs of ONE, never a run of two. Two of the last four is satisfied at the
third frame. Swept over all three sessions it recovers two of the four cards and changes no
other verdict; 2-of-3 and 3-of-5 both recover fewer.
**A settle may only complete on a frame that is itself quiet**,
because the fire photographs that frame — measured, it costs nothing, and without it a
capture could be taken from a frame the machine had just called not-confidently-still.

**The cost is two frames of latency per capture**, ~84 ms at the observed 24 fps, against a
623 ms feeder period with ~400 ms of stillness in it. Re-scored, the five pre-D81 traces
reach byte-identical verdict counts, so the confirmed 85/85 run is not re-litigated.

### Ruling 2 — the stall clock is cleared by a COMPLETED settle

The clock was cleared by any single frame under tLo while a fire needed two in a row, so the
alternation above reset it every other frame and it could never expire.
**Across three sessions and four cards left in front of the lens unphotographed, `stalled` did not fire once.**
The one signal built to mean "something is there and I am not capturing it" was structurally
blind to the only case that produced it.

Cleared on a settle instead, it reports each of them: one stall per session, every one on a
real card, and
**zero false positives across 67 good captures and the 217 verdicts of the five earlier traces**.

**This is the ruling that matters most, and it is deliberately not a capture.** Two of the
four losses had one quiet frame in ten — those scenes were genuinely moving, the operator's
hand still on the card, and no threshold should photograph them. Ruling 1 recovers the two
that were still; this one makes the other two loud. Together the four silent losses become
two photographs and two sentences on the HUD, which is what §5.5 asks for.

### Ruling 3 — `presenceMin` is 16.0, and it is sized to a hand

**D81's own derivation of 8.0 did not survive re-measurement, and this entry corrects it rather than extending it.**
8.0 was set by illumination drift — a static scene walking 7.94 from a baseline seconds old. An undisturbed stand does not creep at all. Per-second worst
dBase, plate only:

    21:10   0s 2.45  1s 2.26  2s 2.53 … 9s 2.36 │ 10s 8.12  11s 14.14  12s 17.91
    21:16   0s 2.13  1s 2.19  2s 2.20 … 5s 2.79 │  6s 6.81   7s 14.66   8s 11.64

Everything above 3 is **the operator's hand entering frame with the first card**. It holds
still for two frames on the way in, and at 8.0 that fired. 16.0 is 1.4× over the worst
approach measured (11.15) and 2× under the quietest card in the same sessions (32.5);
re-scored end to end it removes exactly the two junk fires and nothing else.

**It is a constant and it is now the binding term, and that is a debt rather than a design.**
`presenceK × dTypical` sits at 6–10 on this rig, so this floor decides every verdict and D81's adaptive half decides none — the species D81 convicted in `cardLumaFloor`,
reintroduced knowingly. It stays constant because what it must clear is a HAND, whose size
in frame no session statistic measures.
**Three quantities re-derive it on a new rig and they are the three above**:
the idle stand, the worst approach, the quietest card. Nothing
in the machine measures the second, which is why this is written down instead.

### What is enforced rather than asked for

`make docs-audit`'s **`motion params`** row reconciles `app/src/motion.ts`'s `DEFAULT_PARAMS`
against `scripts/score-trace.py`'s mirrored constants, both directions, with an accounted-for
list for the one parameter the offline scorer deliberately does not carry.
**That row was claimed before it existed**:
`score-trace.py` has said since D81 that the audit keeps the two honest, and there was no such row, while this entry widened the mirror by two more constants.
A comment naming a check that does not exist is worse than no comment — it is the reason the
next session does not write one.

The three traces are banked and T9 grades them: that the floor refuses exactly the two
settles that photographed the bare stand **and nothing else that fired**,
asserted by time rather than by count, because "two fires are refused" would pass just as happily if the floor
had climbed far enough to refuse two cards instead.

**What would reopen this:** a rig whose hand approach reads above 16, or a card that reads
below it. Either is one trace away from being visible, and the answer is not a fourth
constant — it is a measurement of the approach the machine can take for itself, which this
rig's stand is too quiet to have taught anybody how to do.

## D85 — The corner is settled by geometry, and a variable nothing sets is not a fallback

**Built 2026-09-01, from a screenshot the owner sent while pricing box 4.** The pricing screen
had gone to pieces under them mid-run: stray letters strewn across the ship bar, the emit
receipt and the card rows drawn through each other. Reproduced exactly against a copy of
`runs/2026-09-01-box4-01`, then measured rather than eyeballed.

### What was actually wrong

`bbf7e11` (merged to main 2026-09-01 as [#95]) reordered the pricing row and moved `T` and `H`
into the row's left gutter — which is the **bottom-left corner of the screen**, and three other
things already lived there: `.pricehistory` and `.pricing-photo`, both `position: fixed` at
`z-index: 20`, and `.pricing-ship`, `position: sticky` at `z-index: 10`. That commit noticed the
first collision and settled it with a stacking order, raising the two buttons to `z-index: 21`
so the panels could not swallow their clicks.

**It inverted the defect instead of removing it.** At 21 the buttons draw over the panels *and*
over the ship bar. Hit-testing an 8px lattice on the real screen:

| | points a hidden `.pricing-row` answered for |
|---|---|
| inside the ship bar, receipt up | **48** |
| inside an open reading | **143** |

Those are not cosmetic. `elementFromPoint` at the bar's left edge returned a scrolled-away
row's `H` — so a press aimed at the bar took a **hold** on a card nobody could see, and a hold
writes `decisions.json`.

### Ruling 1 — four things wanted one corner, and a stacking order cannot arbitrate that

Whichever element wins a `z-index` contest, something a hand is aiming at stops answering.
There is no ordering of these four that is correct, because all four are simultaneously
visible and all four are pressed. The contest was run once and produced a worse screen than
not running it.

**So the overlap is removed rather than ordered.** `.pricing` publishes
`--pricing-gutter` — the page's padding plus the two button columns and their gaps, composed
from the same `--pricing-btn` the grid template reads — and both fixed panels start there. No
panel is ever over a `T` or an `H`, and the buttons carry no `position` and no `z-index` at
all. **The absence is the fix**; a row's controls stack like everything else in the document.

Derived and never typed: a hand-written `104px` is the two-declarations-that-must-agree drift
`Pricing.css` already refuses for its grid template, arrived at from the other end.

### Ruling 2 — `--pricing-ship-h` is measured, because a fallback is not a value

D54 positioned both panels above the ship bar with
`bottom: calc(var(--pricing-ship-h, 64px) + var(--s4))`.
**Nothing has ever set `--pricing-ship-h`.**
Three declarations across two stylesheets read it; `getComputedStyle`
returned the empty string. Every one took the `64px` fallback, against a bar that measures
**125px closed and 433px with an emit receipt up**.

Wrong in the direction that buries the bar's own sub-threshold controls — `At the $0.40
floor`, `A flat price`, and the flat input — under the reading panel. Those are the answer
`emit` refuses to run without. All three took no press at all: hit-testing each one's own
centre returned `.pricehistory`.

`Pricing.tsx` now publishes the bar's measured height from a `ResizeObserver`. The bar grows
when the receipt lands, when a refusal is drawn, and when the window narrows enough to wrap
its rows — none of which re-renders the component, so a one-shot measurement at mount would be
wrong and would report as green.

**The panel shrinks rather than overlapping when the bar is tall.** `PriceHistory.css`'s
`max-height` already subtracted `--pricing-ship-h` and had nothing to subtract; with a real
value it does what it was written to do. That is the right trade: a reading is a transient
overlay, and the run's answer controls are not.

### Ruling 3 — the missing check was geometric, and it is asked by hit-testing

`app/tests/pricing.spec.ts` was **56 passed** on the broken screen. Typecheck green, lint
green, `make check` green. Every case in it was still true: they assert text, grid templates
and row heights, and none of those moved.

Three cases were added and each was **run against the pre-fix tree and failed** — 48
punctures, 143 punctures, and a published height that was the empty string.

They hit-test rather than compare rectangles, and that distinction is the entry's point.
`fulfillment.spec.ts:648` has an `overlaps()` helper and it is deliberately not reused here:
two boxes intersecting is the normal, correct state of an overlay above a list. The fault was
never the intersection — it was **who answered inside it**. `elementFromPoint` asks what a
hand aiming at a pixel actually reaches, which is the property that broke, and it is
indifferent to how a later change breaks it: a stacking order, an anchor, or a width.

**What would reopen this:** a fifth thing wanting the bottom-left corner. The gutter has room
for the panels and the bar and nothing else, and the answer would not be another offset — it
would be moving one of them to a corner it can have alone.

[#95]: https://github.com/shivinate7/pkmnscan/pull/95

---

## D86 — The pricing answer is one file for the store, and the worklist spans runs

**AMENDED THE SAME DAY IT WAS BUILT, ON THE OWNER'S QUESTION.** Shown the fan-out write and the conflict detector below, they asked: *"why can't it be my front end is largely a pricing corpus/dashboard of everything, with boxes feeding it? why is it we've made a federalist state system when this is best done as a centralized system?"*

They were right, and this entry had already written the evidence down without acting on it. `runs/<n>/decisions.json` held **two kinds of fact in one file**:

| scope | keys | what it is |
|---|---|---|
| run-wide | `rule`, `basis`, `sub_threshold` | arguably a property of the lot — D48's argument |
| **per-SKU** | `overrides`, `no_market_data` | **a property of the CARD** — D7's argument |

The second half is what a price *is*. TCGplayer prices per SKU globally, D7 states *"price is per-SKU and shared across copies"*, and `pipeline/join.py` spends the live cap against every box at once. Stored in a run directory, one card carried one answer per drawer it had ever been photographed in.

**`pipeline/corpus.py` is the home, and `inventory/prices.json` is the file.** Keyed by SKU, holding the policy too on the owner's instruction, with a per-run policy override kept for the lot that genuinely differs — which is D48's argument surviving in the one place it is actually about. `Corpus.for_run`/`scoped_to` project it into a `Decisions`, so `join`, `emit` and `prices_for` never learned that answers moved: the property D48 spends its length protecting, applied to this move.

**D49 AND D62 BOTH NAMED THIS GAP AND NEITHER CLOSED IT.** D49: *"no durable home for a hold outside the run directory; no cross-run view of what is being held."* D62: *"No cross-run view."* `pkmnscan prices show --held` is one line now.

**What the amendment DELETED, which is the useful part.** The first build answered the duplication with machinery: a fan-out write into N files, conflict detection on every row, and an agreement refusal before a merged file could be written. All of it existed only to reconcile a duplication. `pipeline/merge.py`'s first version carried a `PriceDisagreement` and, run against three real runs, **refused on 66 SKUs — almost every one of them the market having moved between two joins rather than any disagreement at all**. Reporting a defect is worth less than making it unrepresentable.

**What survived whole: the cap.** It is arithmetic over positions, not an answer, so centralising changed nothing about it — see "The cap is D59's defect one register up" below.

**`pkmnscan prices adopt` is the migration**, and it previews by default because there is a real decision inside it. The owner's ruling was newest-wins; three of the eight contested SKUs are a `withheld` hold answered by a later price, and newest-wins resolves those **to the price** — the direction that cost money. The command names those three rather than counting them.

**A legacy run file is never read as a fallback.** That would put the duplication back on the first re-join of an old run. `join` and `emit` refuse with a sentence naming the command instead.

**Amended 2026-09-02: the refusal is unconditional, the migration retires what it folds, and the per-run editor is deleted.** The refusal above was gated on an EMPTY corpus — `join` and `emit` looked for a legacy file only while `inventory/prices.json` held no answers — so from the first adoption onward eight files on the owner's store were silently ignored while this entry and CLAUDE.md described a refusal. It is unconditional now and fires before anything is read or written, naming `pkmnscan prices adopt --write`. That command RETIRES each folded file to `decisions.json.adopted` (`cli/runs.py:retire_decisions`, never overwriting); a re-adopt over SKUs the corpus already answers keeps the corpus's answer, reports the file's under `kept`, and retires the file without `--force`; and `--force` folds the files OVER the corpus rather than into a fresh one — the old form dropped every answer written on `#/pricing` since adoption. `PUT /pipeline/runs/<name>/decisions`, the `#/runs` textarea and `remembered_sub_threshold` are deleted: they answered 409 for every run made after this entry, because `join` no longer wrote the file they edited. The policy's default is D9's amendment of the same day.

---

**The original entry follows, with the parts the amendment retired marked where they stand.**

**`#/pricing` opens on every run that still has pricing in it, merges the same SKU across them into one row, and — ~~writes one answer into every run's own `decisions.json`~~ RETIRED, see the amendment — writes one answer into the corpus.** Built 2026-09-01 on the owner's instruction: *"if I capture from multiple boxes, they ought to be processed in pricing at the same time"*, with the general form beside it — *"items that aren't processed ought to have the functionality of being processed all at once"* — and the boundary they set on it, that pricing by box is good too and must not be lost.

**This is D48's own resolution one register over, and it overturns nothing.** That entry ruled a send is a cart of boxes and a run is still one box, because *"a run carries a reading, a `--bypass` ruling and a `decisions.json`, and all three are properties of what is IN the drawer"*. Every word stays true. The **view** merges; the **file** does not. One answer to a merged row is one `PUT /pipeline/runs/<name>/decisions` per run holding that SKU, the route is untouched, and nothing downstream learns a new shape — the property D48 spends its length protecting.

**~~One answer to a merged row is one `PUT` per run holding that SKU.~~ RETIRED.** There is one document and one write. The sentence stood for about four hours.

**Nothing in D49 argued for the single-select this replaces.** That entry defends where the run comes from — *"a picker here cannot disagree with anything"*, because `GET /pipeline/runs` is the single source — and says nothing about how many may be picked. A set over that same single source has the identical property. D39's one-mass-select rule is about **cards** and is untouched; `#/inventory` still owns the only one. `useState<string | null>` was the cheapest thing to write on 2026-08-30 and no entry defended it.

### What it costs today, measured rather than argued

Across the eight runs in `runs/` on 2026-09-01, **78 of 423 SKUs sit in more than one run** and **8 carry an answer in more than one**. Three of those eight are a `withheld` hold answered with a price in a later sitting:

| SKU | Card | Earlier run | Later run |
|---|---|---|---|
| 9191210 | LeBlanc, Everywhere At Once | box3 08-31 `{withheld: bullish, watch_above: "5"}` | box4 09-01 **`"3.45"`** |
| 9405228 | Death Mark | box3 08-31 `{withheld: bullish}` | box3 09-01 `"2.29"` |
| 9422429 | Public Execution | box3 08-31 `{withheld: bullish}` | box3 09-01 `"2.29"` |

LeBlanc was held bullish above $5 out of one drawer and listed at $3.45 out of another the next day, below the operator's own watch. That row drew as an ordinary listable one — `at_cap: false`, `nothing_to_add: null`, no note anywhere — because a hold lives in its run and dies with it (D49) and no screen had ever read two runs at once.

**D49's stated reopening measurement was the other direction and has never fired.** It watched for *"the same SKU withheld in two runs over one box"*; that count is zero. It is the asymmetric case that bites, and **this entry replaces the measurement rather than repealing it**: what to watch is a hold in one run answered with a price in another.

**Four of the eight pairs were not disagreements at all** — `0.5` against `.5`, the same figure typed with and without its leading zero. `_same_price` compares as `Decimal`, so the flag means something when it fires.

### The cap is D59's defect one register up

`pipeline/join.py:add_to_quantity` spends `live_cap - copies_out` **per run** against a cap that is **global**, so runs joined before either emitted each spend the same room. The 2026-09-01 cart joined boxes 3, 4 and 5 in the same second; five SKUs' per-run claims sum past four, and two reached `pushed: 6` in `inventory/inventory.json` against `LIVE_QUANTITY_CAP = 4`:

    Void Assault (9197754):  pushed: 6, live: 1
    Deathgrip    (9038187):  pushed: 6, live: 1

D59 fixed per-**box** capping inside one join and this survived per-**run** across joins that never saw each other. `GET /pipeline/pricing` computes the figure once — `min(claimed, cap - copies_out, copies)` — and reports `claimed_add` beside it so the row says the runs disagree with it. **It corrects nothing on disk**: this route writes no import file, and the emitter is where the arithmetic has to change.

**`copies` is the distinct positions and not the sum.** Box 3 has been joined three times, so summing each run's count made Void Assault twelve copies of a card there are seven of.

### What the picker became

**A filter over the list rather than a gate in front of it**, and it draws a **remainder**. `counts.skus` is the size of a job and never the job — box 2's 109 SKUs are one `floor` press and box 3's 199 are 117 real decisions. `counts.sub_threshold` and `counts.no_market_data` had ridden every poll since the manifest gained them and were read by nothing; the roster asks `Decisions.blocking`, the Python that actually refuses an emit, so the chip cannot claim a refusal Python does not make (D49's rule over `readiness.ts`, applied to the server).

**The terminal state D49 predicted and the screen never got.** That entry read the history and said the honest reading was *"a screen whose job is to report there is nothing to do"*. It could never say it: the only empty state fired when NO run had ever been joined, so eight fully-answered runs drew eight chips and cost ~909KB and sixteen round trips to discover they owed nothing.

**Boxes ascending inside a sitting.** `GET /pipeline/runs` sorts by directory name reversed, so within one day the picker drew box 5, box 4, box 3 — backwards against the rule `Runs.tsx` states for the same choice, *"the order they sit on a shelf"*. Two screens ordering the same drawers two ways is drift; it is pinned now because it is otherwise invisible.

### Three defects found on the way, two of them live before this entry

- **`inFlight` became a `Set` and an empty `Set` is truthy.** The emit guard read `if (dirty || saving || inFlight.current) return`, written against a boolean, and so became *always return* — the press silently did nothing. Caught by four cases already in `app/tests/pricing.spec.ts`.
- **The hash was read in an effect, so mount fired two loads.** Whichever landed last won `docs`, but `savedDocs` is a ref written outside React's batching, so a render could see the first load's documents against the second's saved marker: `dirty` went true with nothing typed and the screen PUT a document the operator never touched — **the one write D49 calls the load-bearing absence of the whole screen**. The hash is now read in the `useState` initialiser and a generation guard drops a stale response.
- **`unsaved` must not be memoised.** `savedDocs` is a ref, so a `useMemo` keyed on `[loaded, docs]` never recomputes when a write *lands*; the save loop oscillated unsaved → saving… → unsaved forever.

### What is NOT built, named rather than left to be discovered

**The merged emit is not built.** The owner asked for one CSV — across runs, across the listed/sub-threshold split, and across games, with a checkbox to peel off just the above-threshold rows. It is a real change to `pipeline/join.py`, `cli/resolve.py` and `cli/cmd_emit.py`, because **a merged file cannot be a concatenation of the CSVs already on disk**: the cap has to be recomputed across the union or it writes the over-push above into a file. Until it lands, `emit` stays per run and the press is **absent** on a worklist of more than one — absent rather than disabled, which is D33's rule for the control that spends applied to the one that writes files.

**Whether TCGplayer's Import to Staged accepts a file spanning two `Product Line`s is still unknown.** `cli/runs.py:import_listed_name` has said so since it was written and `fixtures/staged-import-accepted.csv` proves it for one line only. The owner has said they will test it. Nothing here depends on the answer.

**The two already-over-pushed SKUs are not corrected.** Fixing the arithmetic does not un-list what TCGplayer already holds; that is the owner's to reconcile.

**What would reopen this, and there are two.**

*A worklist that is never used with more than one run.* The remaining cost of the merge is the union and the cap arithmetic; if every sitting is one box forever, the honest simplification is the single-select again. The measurement is whether any `GET /pipeline/pricing` is answered with more than one run in it.

*A lot that genuinely wants its own policy.* `Corpus.overrides` keeps a per-run `rule`/`basis`/`sub_threshold` for exactly that, and **nothing writes one today** — no screen offers it and the migration never produces one. If the field is still empty after several sittings it is speculative generality and should go, taking `_agree_policy` and its refusal with it. If it fills up, D48's per-lot argument is stronger than this entry credits and the policy belongs back in the run.

**What is still NOT built.** The reconcile is per run: `cli/cmd_reconcile.py` scopes its diff to one run's `emitted_skus`, while the thing it diffs against — `store/master.py`'s `Listing` — is already per SKU across every box and run. The owner named the consequence: a full live TCGplayer export should reconcile across every emit, box and date at once, and report **both directions**, which is that command's own rule. It would be the first thing able to see the two SKUs this entry measured at `pushed: 6` against a cap of 4. Not built here.

---

## D87 — The reconcile is store-wide, and what it writes is `live`

**One full TCGplayer live export settles every SKU in the store, whatever run or box it came from, and reports both directions.** Built 2026-09-02 on the owner's instruction, after D86 moved the pricing answer into one corpus: *"if you've tracked what all's been emited, then if i ever get an export of my entire live tcgplayer inventory, it should be able to auto reconcille across emits/boxes of any times."*

**The asymmetry that made it cheap.** `cli/cmd_reconcile.py` scopes its diff to one run's `emitted_skus`, but the thing it diffs against was never run-scoped: `store/master.py:Listing` holds `pushed`/`staged`/`live` **per SKU across every box and run**, and D7 amended says so — *"quantities held against a SKU rather than states a card wears"*. The scoping was a property of the command, not of the data.

### What it found, on the owner's own store

Measured 2026-09-01 against a real My Pricing export, 757 rows:

| | |
|---|---|
| SKUs with a listing record | 443 |
| **carrying pushed copies with `live: 0`** | **405** |
| `staged`, anywhere | 0 |
| SKUs over the 4-copy cap | 2, at `pushed: 6` |

**Reconcile had effectively never run.** So `pipeline/join.py`'s cap arithmetic was working off `Total Quantity` from whatever export a run happened to hold, with the store's own `live` contributing nothing at all. After the settlement it sees **1,079 live copies where it saw 93**.

### What it writes is `live`, and only `live` — which is smaller than it first looks

The first build settled `pushed` too, drawing it down by what the export accounted for. That was wrong twice over and the second pass is what proved it.

**`pushed` is CUMULATIVE, not outstanding.** It counts copies ever written into an import file, an import file holds the last delta only (D54), and the per-run reconcile is the only thing that draws it down. On a store that never reconciled it is *the only record of what was sent*. Rewriting it destroys that.

**And `cli/resolve.py:_copies_out` already corrects a stuck one**, in its own words: *"THE CEILING IS PHYSICAL, AND IT IS WHAT CORRECTS A STUCK `pushed` … it cannot be true that TCGplayer holds more copies than we sent and have not sold."* What that arithmetic was missing is a real `live` — **which nothing in this repo has ever written**. Populating it is the whole fix.

**The ledger's own `live` is a stale observation, not a second belief.** Adding it to `pushed` looked principled — `LISTING_STAGES` partitions the sent copies — and is false of this data: **32 of the 38 SKUs carrying a legacy `live` would then claim more copies than were ever captured.** The two describe the same copies at different moments, so the export supersedes it.

**Amended 2026-09-02: the settlement was not wired to the cap, and the next re-join overwrote it.** `_copies_out` read `live` from the export's `live_by_sku` alone and refused the store's — its comment cited D59's *"nothing here knows which of the two readings is the newer one"* — so `--live --write` moved 1,079 copies the cap arithmetic never saw, and "the whole fix" above was a claim about a field nothing downstream read. And `cli/cmd_join.py` set `live` from whatever export the join was handed: run `2026-09-01-box3-01`'s recorded export was fetched fifteen minutes BEFORE that run was emitted, `Total Quantity` blank for every SKU it had just listed and `parse_quantity('')` reading 0, and "Join again" on `#/runs` with the picker left alone — the ordinary path — took a copy of the store from 1,072 live copies over 406 SKUs to 700 over 266. Closed by D59's amendment of the same day: `Listing.live_as_of` dates every reading, `Listing.live_reading` arbitrates the cap and `Listing.observe_live` the write, the join and reconcile reports name what they kept, and an uploaded export carries `File.lastModified` so its stored copy is dated to the file rather than to the upload. A settlement row was written before the field existed, and `Listing.from_record` reads its `at` as the observation time at the parse — absent is legacy, null is a record nothing has read `live` for, and the two are told apart nowhere else.

**Idempotence is the test that separates the two designs.** A settlement that rewrites `pushed` destroys the record it read, so its second pass answers a different question — measured, 126 unexplained on the first pass and 120 on the second over an unchanged store. Writing only `live` gives 55 both times, and 0 corrections on the second.

### The residual is a sentence, never an adjustment

**55 copies across 32 SKUs** were sent, are not live, and no card is marked sold. That is genuinely ambiguous — sold and unmarked, pulled by hand, or a row the portal rejected — and this command names them and changes nothing.

**The owner's order list settled what it is.** They estimated *"under 25 cards"* pending; the ledger said 55, and both were right about different things. `Ready to Ship` is **2 orders** awaiting shipment. The 55 is every copy that sold and was never marked, shipped or not. The corroboration is arithmetic: the first emit was 2026-08-22, so every pushed copy left inside that window; the window holds **93 non-cancelled orders** against **123 departed copies** — 1.32 cards per order.

**IT MOVES QUANTITIES AND NEVER CARDS (D7).** Which physical copy sold is deliberately unrecorded — every unsold copy is equally sellable and the export could not say anyway — so this marks nothing `sold`. That is the operator's act on `#/inventory`.

### The other direction, which is the half a per-run reconcile cannot have

- **33 SKUs live at TCGplayer this store has never seen**, 61 copies: sealed product, accessories, and singles listed before pkmnscan. Reported and never touched.
- **10 SKUs TCGplayer holds MORE of than were ever sent from here** — Brutalizer at 8 live against 5 copies ever captured. Left alone: this pipeline did not put them there.

`seen` is deliberately **wider than the listing ledger** — every SKU any card carries. A withheld (D49) or not-yet-emitted card has a SKU and no listing, and judging against the ledger alone would accuse the operator of listing it outside pkmnscan the moment it went live.

### Reachable, and where

`#/runs`, under the run panel. That screen's own lede names the four commands; this is the fourth, in the shape that is not run-scoped, and the panel says so. Not `#/inventory`: that is where a card's state changes and this changes none.

**Two presses, and the first writes nothing** — D33's gate pointed at the ledger rather than at the money, and `prices adopt`'s reason: it moves the quantities the cap arithmetic reads, over every SKU at once. The settle control is **absent** until a preview has answered, and the same bytes are sent twice rather than re-picked.

### What would reopen this

*Line-item attribution.* This settles quantities and cannot say which copy of a SKU sold, because the order list is order-level. `server/order_transport.py` (D69) already fetches this account's own orders authenticated; if it can reach line items, the residual stops being ambiguous and the reconcile could mark cards sold — which would make D7's "quantities, not copies" a question worth re-arguing rather than a settled one.

*A `staged` that stays empty.* It is 0 for all 443 SKUs and the only writer is the per-run reconcile. If the store-wide path is the one that gets used, `staged` is a stage nothing occupies and the ledger is really two counts and a record.

## D88 — The store of record is SQLite, and a write is one transaction

**`inventory/store.sqlite` is the master store, every `Store.write()` is one transaction over every table, and a session loads only the rows it names.** Built 2026-09-01, from the owner's plan for a 100,000-card run: the pile is 100,000 raw cards, scanning is the highest-margin activity on the table — measured at $0.00105 per card in API cost against $138–921 of gross value discovered per scan-hour — and two things blocked the run, neither of them strategy. This entry is the first. **This reopens D13**, which said "server-side JSON" without ever arguing for it; D13 carries the amendment and the rest of that entry stands.

### The argument is correctness first, and speed second on purpose

`store/session.py` made the case against itself for a week. Its header said the five JSON files were each replaced atomically and *"the set of them is not one transaction. A kill between two `write_json` calls leaves the store internally inconsistent... The exposure is real at Ctrl-C frequency rather than theoretical"*, named the two honest fixes — *"a staged directory swapped by a single `os.replace`, or a real embedded store"* — and called choosing between them *"a decision nobody has argued"*. D53's supervisor drains in-flight requests before a restart for exactly this hole, and D63's ledger was written LAST so a torn write lost the order feed rather than the inventory — a preference among losses, which that entry says in as many words. **A transaction closes the hole; an ordering only chooses what falls into it.**

The speed argument is real and is deliberately second. **Every capture re-read, re-parsed and re-serialised every card in the store, and synced the whole file to disk.** Measured on a copy of the owner's store grown synthetically, one capture's store cycle under the JSON files:

| cards | read + parse | write | total |
|---|---|---|---|
| 1,560 (the store on 2026-09-01) | 13 ms | 57 ms | 70 ms |
| 10,000 | 67 ms | 309 ms | 374 ms |
| 20,000 | 167 ms | 611 ms | 770 ms |
| 50,000 | 498 ms | 1,616 ms | 2,112 ms |
| 100,000 | 1,203 ms | 3,234 ms | 4,366 ms |

The feeder's measured cadence is 623 ms per card and the client awaits this write inside the capture loop, so past roughly 20,000 cards capture was store-limited rather than feeder-limited, and at 100,000 it was running at a seventh of the feeder's pace. Write-behind would have fixed that alone, more cheaply — at the cost of durability on data that names photographs nothing can regenerate. It was not taken, because it does nothing for the first argument.

### Why SQLite, on this repo's own bar

`requirements.txt` refused `requests` for *"one fewer dependency between a clean clone and a green harness"* and refused opencv twice on measurements. Against that bar, `sqlite3` is stdlib: no new dependency, O(row) writes, one transaction over everything, and a query language a person can use. JSON-per-card or JSONL-with-compaction add no dependency and close no transaction; `dbm` closes neither; LMDB is a C extension with no index a person can query; DuckDB is tens of megabytes of OLAP; Postgres is a service that must be running for `make harness` to pass. **D15 already made this argument for the catalog**: *"SQLite, not Postgres. ~20k rows, read-only after load, one machine... `sqlite3` is stdlib."* Same machine, same single writer. This applies a choice the project had already made to the place that needed it.

### The shape: one payload column, a few indexed columns beside it, and a mapping that is a dict until it is asked to be a database

**Every record is stored whole as JSON text in a `payload` column, exactly the dict `asdict` produces.** The record classes under `store/` gain and lose fields the way they always have — `Inventory.parse` filters on `__annotations__` and `store/db.py` never learns a field's name — so a schema migration is not what a new field costs. Beside the payload sit the INDEXED columns each `TableSpec.columns` derives from the object at write time (`box`, `idx`, `state`, `sku`, `capture_id`...), which cannot disagree with the payload because they are computed from it, and which are what a person queries:

    sqlite3 inventory/store.sqlite "select key, name, state from cards where box = 3"

**`Snapshot` is still the API and `inventory.cards` is still a dict to every caller.** `store/rows.py`'s `Rows` is a `MutableMapping` that is memory-backed for `Inventory()`, `Inventory.parse` and everything T7 drives directly, and bound to a `Source` inside a session — where a point lookup is one row, `where(sku=...)` is one indexed query, and `select(("box", "idx"), box=3)` returns column values with no object built. **The allocator's high-water scan, the capture-id replay, the SKU walk and the box-number allocator ask the mapping for the rows they want rather than walking every card**, and `Inventory.next_index` keeps its refusal on a record that will not coerce by asking for the rows whose `box` or `idx` column is NULL — which is exactly the set `int()` refuses, since the columns are derived by the same coercion. Iterating the whole mapping loads the whole table, which is what iterating a whole table should cost. **A flush is a diff**: every loaded object is re-dumped and compared to the shape it had when it was read, so a session that read one card and changed nothing writes nothing.

Measured after, same synthetic store, one capture's `Store.write()` with `allocate_capture`:

| cards | capture cycle | card objects built | whole-store read |
|---|---|---|---|
| 1,560 | 2.4 ms | 1 | 11 ms |
| 10,000 | 2.7 ms | 1 | 77 ms |
| 20,000 | 2.8 ms | 1 | 154 ms |
| 50,000 | 2.9 ms | 1 | 420 ms |
| 100,000 | 3.3 ms | 1 | 978 ms |

At 100,000 cards the capture cycle is **~1,300 times faster** and stops growing with the store; the whole-store read (`GET /inventory`, a join, an emit) is still O(cards), which is what those operations are. **`synchronous=FULL`**, so every commit reaches the disk before the request answers — the durability the per-file `fsync` had, and the 3 ms includes it. WAL mode is what lets `Store.read()` stay lock-free: a reader sees the last commit and never a torn one, and holds nothing a writer waits on.

**The flock stays, and the transaction is inside it.** `files.exclusive` guards more than the tables: callers unlink photographs, rename sidecars and upsert `codes.jsonl` inside `Store.write()` on the strength of that lock, and none of that is in a table. A crash between a file write and the commit still leaves a file the store does not describe, exactly as before — `do_delete_box`'s money rule is unchanged — and D53's drain is still a prerequisite for the watcher for that reason.

**The history is the `events` table, still append-only, and it commits with the change.** `history.jsonl` was appended after the files, so a crash between the two under-reported history; a row now lands in the same transaction as the state it describes. `Store.history()` still refuses the whole log over one unreadable row, so `_sale_origin`'s degrade-to-unknown path is unchanged and T7 still holds it there.

### The migration is automatic, lossless, reversible, and never a fallback

**The first open of a legacy store imports it**, under the lock, through `Inventory.parse` — which is where the D10 v1→v2 card-state migration has always lived, so a v1 file crosses both in one read — and moves the six JSON files to `inventory/legacy-json/` with a `MIGRATED.json` receipt naming each file's digest and byte count. The database is built under a temporary name and renamed into place before any file moves, so a crash at any point before the rename leaves the JSON exactly where it was. **Reversing it is deleting `store.sqlite*` and moving `legacy-json/*` back up one level**, and the receipt says so. **Measured on a copy of the owner's real store**: 1,560 cards, 443 listings, 1,560 paid answers, 232 queue entries and 7,450 history events imported in 0.13 s, and every part read back through the database compares equal to `parse()` of the original file — the T7 case that pins this uses a record carrying a field no dataclass declares, which the same filter drops on both paths.

Automatic rather than a command, unlike D86's `prices adopt`, because there is no decision inside it: D86's fold had eight SKUs answered two ways and three holds that lost to a price, and a person had to see that. This is a re-encoding, and the receipt is what a person sees.

**A legacy file beside a live database is never read** — D86's rule for a legacy run file, applied here. `make status` reports one; nothing else notices it. The cost of this ruling is that a hand-restored `inventory.json` does nothing until the database is deleted, which is the same cost D86 accepted for the same reason: a fallback that is sometimes read is a duplication waiting to disagree.

### What is enforced

`harness/tests/t7_store_and_seams.py:check_store_of_record` holds the three claims: the queue table's write raising after the card table's leaves NEITHER row committed and no history row either; a capture into a 61-card store builds at most two card objects and never loads the table; and the legacy import reads back equal, moves every file, receipts the counts, and ignores a file put back beside the database. Every case in that file that used to compare a store file's bytes compares the table's rows now, and every case that seeded `history.jsonl` by hand seeds the `events` table — the argument for each is unchanged and is in the case.

### What it costs, and what is deliberately not done

**State stops being greppable as text.** The owner ruled `sqlite3 .dump` and a `SELECT` sufficient and that no JSON export target is wanted; `to_payload()` is still the wire shape of `GET /inventory`, so a JSON view of the inventory is one request away, and that is not a target.

**`Store.history()` still returns every event.** The sale and retirement reversals read the whole log to find one position's last state, which was O(history) under the file and is O(history) now — 42 ms on the owner's store, and a position-scoped read is one indexed query away when it matters. Not built here, because nothing measured it mattering.

**The whole-store read is still O(cards)**, and `GET /inventory` at 100,000 cards is ~1 s. That route is polled; the honest fix when it bites is a box-scoped read, which the `cards` table's index already supports.

**What would reopen this: a second writer that is not this process.** The flock and the WAL both assume one machine and a local filesystem, which is the assumption the NAS entry under Someday already refuses to break, and SQLite over a network filesystem is the classic way to corrupt one.

## D89 — A sold card's photograph is reclaimed on purpose, and the record keeps its digest

**`POST /boxes/<box>/photos/reclaim` deletes the photographs of a box's sold cards, keeps every record, and writes the photograph's digest onto the record before the bytes go.** Built 2026-09-01, the second of the two things the owner's 100k plan named as blocking the run. Photographs measure ~1.8 MB each — `captures/` is 2.7 GB for ~1,560 cards — so 100,000 cards is ~176 GB, and if ~95% sell or go out as bulk and are reclaimed per batch, the retained set is ~9 GB. The owner's ruling: **records are permanent, photographs are disposable once a card is sold through.**

### The operation did not exist, and it is a third shape

`_unlink` ran only in the capture-undo path, which deletes the RECORD as well (D10). `sold` and `retired` both keep the photograph (D26). Record kept, photograph reclaimed is the shape between them, and it is a new one rather than a softening of either: D10's undo is a card that was never captured, D26's states are a card that left with its evidence intact, and this is a card that left and whose evidence is now the digest rather than the bytes.

**Sold only, and the boundary is the store's.** A retired card's photograph is what lets the retirement be questioned later — D26 says so — and a card on hand needs its photograph for the pull preview (D6). `Inventory.record_photo_reclaimed` refuses any state but `sold` with `CardNotSold`, so a caller that bypassed the route cannot reclaim a photograph a screen still needs; the route filters to sold cards with a photograph on disk before it asks. The sidecar stays: it is the operator's claims, a few hundred bytes, and `identify.sidecar.scan` keys on the photograph, so a sidecar with none beside it is inert.

### What the record keeps, and what D36 gives up

**`photo_sha256` and `photo_reclaimed_at` are set together, by this operation and nothing else, and are null while the file is on disk.** While the photograph exists the file is the fact, and a copy of its digest on the record would be a second thing to keep true through D26's re-shoot. Once the bytes are gone the digest is the only trace of what was photographed. The `photo` path is kept too, so `photo: null` goes on meaning "never photographed" — `emit` records such cards — and a screen that finds `photo_reclaimed_at` set draws *reclaimed*, which is a different fact from *missing*: one is a store that gave something up on purpose, the other is a store that lost something. `BoxBrowse`'s photo panel says which, with the stamp and the digest.

**D36 made the photograph the truth and `photo_sha256` the binding between a run and a slot**; a box whose sold photographs are gone can no longer be re-bound that way FOR THOSE CARDS. That is given up here deliberately, for cards that have left the box, and it costs less than it reads: `cli/resolve.py:realign` reads a reclaimed card as *departed* — the digest on the run record is on no photograph in a box whose other photographs are present — which is the truth, it sold. T7 holds that outcome. A box reclaimed whole reads as *unverified* and passes through, which is D36's existing answer for a box with nothing to check against.

### It gates, and it is shaped like the release rather than the delete

There is no undo — the bytes are gone and the card is not in your hand — so this sits with the whole-box delete under `docs/DESIGN.md`'s *"genuinely destructive actions may still gate"* clause. The gate is D34's preflight shape: `GET /boxes/<box>/photos` answers the free count — sold cards whose photograph is on disk, the bytes they hold, the cards already reclaimed, and the on-hand photographs a reclaim does NOT touch — and the control that fires **does not exist** until it has answered, absent rather than disabled. Both presses name the box. `confirm: true` on the wire, for the release's reason: the route's whole content is a person's decision that these photographs are disposable, and a request must say so on purpose. A second press meets `nothing_to_reclaim` rather than a silent zero.

**Reachable**: `#/inventory`'s box operations, above the delete and below the release, drawn only for a box holding a sold card. The route, the client functions, the control, the receipt naming every key, and the panel's reclaimed sentence all landed together, which is `CLAUDE.md`'s route-is-not-a-feature rule observed rather than owed.

### What is not built

**No store-wide reclaim.** The plan's own shape is per batch — reclaim as each 5,000-card lot sells through, so the peak stays near 9 GB rather than climbing to 176 — and a box is the batch this product has. A whole-store press is one loop over `GET /boxes` away if the per-box gesture turns out to be resented, and the history of the box delete says what a resented gate becomes.

**No probe of the pile.** Neither this entry nor D88 measures whether the 100,000 cards are worth scanning; the 2,000-card probe that decides it is work at the rig, and it needs none of this — at 2,000 cards the JSON store was 25 ms. This is the second half of the plan built ahead of the first, on the owner's instruction to execute the plan end to end, and it is recorded that way rather than as the probe having been done.

## D90 — The envelope is the unit of the write, and an order drives the walk as a mode of the inventory screen

**An order takes over `#/inventory`: the walk lands on the first copy that order needs, an arrow steps to the next, and the whole order is recorded on ONE press that says the envelope is filled.** Built 2026-09-02 on the owner's want: *"as orders arrive on TCGPlayer I want them to be matched against PKMNSCAN for SKUs they may hit, and then I literally want to be able to have all the cards pulled either in one go across all orders or work order by order with basically an order fulfillment screen showing me one after the other without me searching for each card"*. Both halves of that sentence are modes — `#/inventory?orders=open` is the one go across all orders, `#/inventory?order=<key>` is order by order.

**The mechanic was asked for by name, and it is the mechanic that already exists.** *"you know how currently in inventory if you're on one card and left or right arrow you go to the cards next to you in the box, and when you move from card x to card y, you also went from seeing all the positions card x was in to now seeing all the positions card y is in, i want that same mechanic on the order walks too"*. The arrows step the queue instead of the box while a walk is on — consulted by `BoxBrowse`'s existing window `keydown` listener, after its existing guards, so there is one key table and one listener — and the copies panel follows the focus for free, because that is all it has ever done.

### The unit of the write, and the failure it exists to end

**The owner named their own error point and rejected the obvious remedy in the same breath.** *"does order driving the walk mean mark sold is auto applied / auto matched? i'd rather it be i can't move on from the envelope until I click a button saying the envelope is filled all items mark sold something like that, yanno? currently i think my biggest error point might be remembering only after i've already switched to pulling another card that oh did i even mark the previous card sold?"*

**So the walk writes nothing per card.** No advance records anything, no arrow spends a copy, and `POST /orders/fill` records every copy of one order — pulled and sold — on the press that says the envelope is filled; in order mode the next order is not offered until that press lands. The state the owner described is unrepresentable rather than recoverable: there is no moment at which some cards of an envelope are recorded and others are not, so *"did I even mark the previous card sold"* has no true answer that is not the whole envelope.

**Auto-applying the sale on the advance was the alternative and it reproduces the doubt one register down**: instead of wondering whether a card was recorded, the operator would wonder whether an arrow pressed twice recorded twice. An advance is a statement about where the eyes are; a press on the envelope is a statement about what is in it.

### This reopens D69 on the owner's word, and what moved is the unit

**D69 ruled `One card, one press, and there is no batch control.`** That sentence stands over `POST /orders/pull`, which is untouched: one SKU, its copies, its own undo, its receipt. What this entry moves is the unit of the write for the WALK, and it moves it on the owner's instruction rather than on an argument D69 got wrong.

**D69's ruling was about a screen that lists picks, and a list is not a pass through drawers.** On `#/orders` the operator reads rows and presses the one they just fetched, and one card, one press is the honest gesture there. The walk is a different posture: minutes at a drawer, hands full, eyes on cardboard. The envelope is the unit the OPERATOR works in, and D69 had no walk to notice that from.

**What did NOT move, and it is most of the machinery.** Every copy is still aimed by its own `capture_id`; the aim is still checked against the card actually at that slot (`capture_id_mismatch`, rather than selling whatever slid into the index after a mid-box delete — D10 ruling 1, D58); the SKU check and the duplicate guard are the same code, because `_prepare_targets` and `_ledger_pull` were lifted out of `do_order_pull` and both doors go through them. `ORDER_FILL_TARGET_LIMIT = 50` bounds one press.

**N calls to `/orders/pull` were the cheap build and they were refused for a reason that is not taste.** That route takes one SKU per call, so a three-line envelope is three writes, and a refusal on the second leaves a half-recorded envelope the undo cannot reverse in one press: `/orders/pull`'s undo NAMES no line — it discovers the holder from the ledger — and refuses `pull_spans_lines` the moment the copies belong to two of them. The operator would be left pressing undo once per line, in the right order, after a failure. One transaction, one refusal (`fill_entry_refused`, naming the line and the position, with nothing written), one undo (which names its lines and refuses `fill_line_mismatch` if the ledger disagrees).

**D39's one-mass-select rule is not reopened.** This is not a multi-select over cards; nothing on the screen is ticked to compose it. The envelope is the resolver's own answer for one order, and the press either records that answer or refuses it whole.

### The queue is of lines, and wave mode sorts by position without drawing one

**T6's first determination ruled `A queue of positions would stand a second pick list beside the panel already drawn`, and wave mode sorts stops by `(landing.box, landing.index)`.** That reads like the determination being ignored and is not: what the sentence protected is the second-RENDERER rule, and it is intact. Nothing new is drawn. A stop is expressed as the walk's own focus through `goTo` (D45), every label is `place.label` off the wire (`pipeline/join.py:Position`, still the one formula), and `app/src/CardLocations.tsx` still draws the copies of whatever the walk points at. The sort decides the ORDER of a queue whose members are still lines; it renders nothing.

**The sort is the argument FOR ordering by position rather than against it.** Order mode walks the drawers in the order the buyer's cart happened to be composed in: all three copies of X, then both of Y. If X sits in boxes 2, 5 and 7 and Y in 2 and 5, that is five shelf changes where the interleaved pass is three — and the interleaved pass is the whole content of *"all the cards pulled either in one go across all orders"*.

**A landing is re-derived on every read, so the pass is a property of the read and never a stored list.** A three-copy line whose first copy was just filled stands at its next unfilled copy the next time the queue is computed; a mid-box delete on another device moves an index and the landing moves with it. `app/src/orderWalk.ts` holds no state, calls no server and imports no React for this reason, and the only thing carried across reads is the cursor.

**A line the walk cannot stand on is counted rather than walked to.** A line still owed copies with no pick the walk can aim at — `no_copies_on_hand`, a pooled copy (D24), a record with no capture id — is `unfillable`: the banner counts it and links to `#/orders`, and the queue never lands on a place that does not exist.

### It is a mode, and D31's ruling against two modes is untouched

**D31's correction was against two TABS over one set of records** — a segmented control asking which way to look at the same 767 cards when there was only ever one question: *"i imagined moreso in this merge that these wouldn't be two tabs, instead it's basically find a card in a box-based system if anything.."*

**A driver is not a tab.** The spine is the same — box, section, card — the photograph is the same, the copies panel is the same, the writes are the same door. What the mode adds is a banner saying which order is driving, a queue the arrows step, and a way out. Nothing is offered twice and nothing has to be chosen between, which is the property D31 was defending.

**It is not a chord either, and that ruling is not touched.** `app/src/App.tsx`'s chord table is a ROUTE table whose own comment rules out a second key space reaching a mode inside a route, and D51 settles Cmd-arrow as the one modifier the shell takes. Entry is a link on `#/orders` — `Walk this order` per open order, `Walk every open order` in its header — and exit is `Stop walking`, drawn ALWAYS LAST in the banner so the press that leaves is never where the press that fills has just been.

### The URL is the handoff, because the order key has one source of truth

**Entry is `#/inventory?order=<key>` or `#/inventory?orders=open`, and not `app/src/runHandoff.ts`.** That `sessionStorage` handoff exists, is D27's carve-out rather than a new one, and would have worked. D49's argument for `#/pricing?run=` is taken here verbatim: the key has one source of truth — the ledger — and a copy of it in a second store is a second thing with its own clearing rules, its own staleness and its own way of disagreeing with the address bar.

**What that buys is T6's own open question answered.** That section closed with *"Whether the queue survives a reload"* and declined to settle it, noting the argument is stronger here than for a run handoff because a pull walk is minutes at a drawer rather than seconds between two screens. It survives: the ask is read out of the hash, the key is validated against the payload on every read, and a reload lands on the first REMAINING stop rather than on nothing or on one already filled. The colon in `source:number` is why the key is encoded.

### The resolver is asked for what is owed, not for what the buyer bought

**`_engine_order` passed `line.quantity` raw and the ledger's recorded pulls were subtracted nowhere, so a partly filled line resolved as if nothing had been pulled.** `Ledger.outstanding` is the quantity that reaches the engine now. The defect predates this work and was live on `#/orders`; it is one this entry found rather than one it pays for.

| the case | before | after |
|---|---|---|
| a line of 3, one copy pulled, 3 copies in the store | wants 3, finds the 2 unsold, reports `short` | wants 2, reports `resolved` |
| a line of 3, one copy pulled, 5 copies in the store | wants 3, allocates **3** picks against a line owed 2 | wants 2, allocates 2 |

**The second row is not a local error, and that is why it is the one that bites.** `resolve_all` is a one-pass allocation over the WHOLE open set and its double-book guard is D69's single most important property. A third pick allocated to a line owed two is a copy taken out of the pool every other order for that SKU draws from, so the visible symptom is a SECOND buyer's line reading `short` over a copy the first buyer is not owed — a wrong answer on a row nobody touched.

**`pipeline/orders.py:OrderLine` accepts quantity zero now and refuses only negatives.** A line owed nothing arrives wanting zero, the engine picks none, and it answers `resolved` with the breakdown still counted — which is how a filled line keeps drawing its figures without a second implementation of the row. On the wire a resolved line gained `owed`, the ledger's figure, beside `wanted`, the buyer's.

### A pulled copy's slot is joined at read time, and storing it would break D36

**`_order_progress` answers `pulled: [{capture_id, box, index}]`, composed per read from `card_by_capture_id`, and nothing writes it down.** The copies panel needs it and can get it no other way: a pulled copy is SOLD, so the resolver offers it in no pick, and nothing else says which slot it came out of. (`SearchCopy` carries a capture id since D93, so a client could now match the ledger's records itself — that would be a second implementation of a join the store is indexed for, and the browser's copy would be the one with no `card_by_capture_id` to be right about duplicates.) The ledger holds capture ids, the walk is keyed by position, and this is the join between them.

**It may never be stored, and D36 is the reason in one sentence: a run directory's slot numbers are not the truth, the photograph is.** A `{box, index}` written into the ledger beside a capture id is a second address for a card, and it goes stale the first time a card in front of it leaves the box (D10 ruling 1, D58) — with none of the recovery D36 gives a run record, which at least carries a `photo_sha256` to re-bind by. Composed per answer it is simply true. `card_by_capture_id` is an indexed lookup under D88; a card that is gone, or a duplicate id the store refuses to guess between, answers nulls rather than taking `GET /orders` down, and `harness/tests/t7_store_and_seams.py` holds the renumber case that proves it.

### Boxes get no say in which copy fills a line

**Told that `Take this one instead` would be fenced to the copy under the photograph and never one in another box, the owner refused the fence: `You're giving boxes too much independence` (2026-09-02).**

**They are right, and D7 had already ruled it: `Every unsold copy is sellable`, and price is per-SKU and shared across copies.** A box-scoped swap would be the one place in the product where a copy's drawer decided whether it could fill an order — while the copies panel draws those copies across boxes precisely because they are interchangeable, and D45 makes each one press away. Any unsold copy of the line's SKU, in any box, may be taken.

**One copy is refused, and it is refused by the ALLOCATION rather than by the drawer.** A copy another stop in the queue already targets — another line of this envelope, or in wave mode another buyer's order — cannot be swapped in. `resolve_all` is a one-pass allocation over the whole open set precisely so two envelopes cannot name one card, and a hand-swap able to undo that would put D69's double-book defect back one register up: both envelopes would count the copy, the first press would take it, and the second would refuse at the server with the operator holding a card the screen had promised them. The row says `for order N` beside the missing button, which is the reason rather than a fence. The test that proves the box has no say and the test that proves the allocation does are deliberately the same case, over two copies in ONE drawer of which only one is offered.

**And the stop FOLLOWS the copy taken.** The landing is the stop's first target rather than the server's first pick, so a swap into another box moves the walk to that box instead of snapping back to the drawer the resolver happened to choose. The two client maps behind it are `targetsOf`'s `retargets` and `excluded` — the copies re-aimed, and the capture ids the operator said were not there.

**In this mode `Mark sold` is hidden on every row, and `Retire` is not.** T6's second determination is the reason and it is the seam the whole feature turns on: `POST /inventory/<box>/<index>/sold` writes card state and NOT the ledger, so a card sold that way while an order drives leaves its line owed forever and the operator ships a card the ledger still wants. Retiring is a different claim about a different card and belongs to nobody's order.

### What it costs

**The mass-select clears on an advance nobody pressed.** T6 named this and it is kept: a shelf change clears the ticks (D31, because the write the selection feeds is box-scoped) and D45 already pays it for a label press. What the walk adds is that the shelf now changes on an arrow, or on a fill that re-derives the queue, rather than on a gesture aimed at a box.

**Re-aims and exclusions are this screen's and this session's.** `retargets` and `excluded` are React state; a reload drops them and the envelope falls back to the resolver's picks. That is deliberate over a store write per swap — a swap is a statement about the next press, not a fact about the store — but an operator who re-aimed three copies and then reloaded gets the resolver's answer back with nothing on screen saying it changed.

**The banner costs about 62px above the walk at every stop.** It renders between `.browse-controls` and `.browse-body`, so the photograph's own floor and everything under it start about 62px lower for as long as the mode is on. It is one row, `nowrap`, and its height never changes — D28's rule that a list must not move under an undo, applied to the row that carries the undo.

**A copy taken without pressing the swap records the slot the walk was standing on.** The envelope sends the targets the SCREEN holds, not the card in the hand. Take a different copy of the same SKU silently and the write is right about the SKU and wrong about the slot: the store says a card is gone that is still in the drawer, and the aim check cannot catch it because the card at the recorded slot really is that SKU. The discipline is the one the walk is built around — take the copy the walk is standing on, or press `Take this one instead` and let the stop follow you.

**It is built over an ingest no real order has ever been through.** Measured against the owner's own store on 2026-09-02:

| | |
|---|---|
| cards in the store | 1,625 |
| cards sold | 104 |
| orders in the ledger | **0** |
| copies ever recorded as pulled for an order | **0** |

All 104 of those sales went through `#/inventory`'s plain sale — the write this mode hides, for the reason those 104 demonstrate: it moves the card and leaves the ledger alone. D91 built the door an order arrives through on the same day, and its own table records the fetch having returned an order zero times before it. Every guarantee here is proven by `harness/tests/t7_store_and_seams.py` and by nothing that has held a buyer's money.

**A row's correction and its reversal share a rectangle, so a double press takes one back.** `.card-locations-action` is right-anchored, `Take this one instead` is about 177px and `Not here` about 84px, and the shorter one lands inside the longer one's footprint. Neither press reaches the server, so there is no busy gate to cover an overshoot the way one covers the sale. This is the same overshoot `Inventory.css` already records for `Mark sold`, decided the same way and for the smaller stake: nothing is written, the row's mark changes word and register, and the banner's `take` figure moves — so the second press is visible rather than silent, and one more press undoes it. What was fixed instead is the part that was NOT visible: with every copy excluded the landing used to fall back to the resolver's first pick and walk the operator to a drawer they had just said the card was not in. It stays where it is now.

**In wave mode the banner is not one height, and the envelopes list is why.** The ROW is constant — that is the measured invariant and the one the arrows are pressed against — but the list beneath it is one 40px row per open order, and a read that changes which orders are open changes it. An envelope filled here keeps its row, drawn `filled`; one another device fills, or one whose last copy leaves the store, simply goes, and the walk below moves up 48px. Order mode has no list and is the constant-height case the measurements were taken in. Fixing it properly means holding a row for an order this screen never filled, which is a claim about somebody else's work that this screen has no business making.

**What would reopen this, and there are three.**

*A second pair of hands.* Everything here assumes one operator at one screen: the cursor, the re-aims and the exclusions are this session's, and two people walking the same wave would each hold an allocation the other has already spent. The measurement is a second device on a walk at the same time.

*A real envelope pressed and found wrong.* The first press against an order a buyer actually placed is the measurement this entry does not have. Watch for `fill_entry_refused` naming a position the operator was standing at: that would mean the aim check and the walk disagree about what is at a slot, which is a store bug wearing this feature's error message.

*`SearchCopy` gaining a `capture_id`.* Today a copy is swapped in only by walking to it, because the aim needs an id the search rows do not carry. If they carried one, an unpicked copy could be taken straight off the panel without the walk moving — worth arguing rather than taking, because the walk-to IS the flow: you look at the card before you swap it in.

## D91 — The window is the range, the status is the filter, and the operator picks it from what the wire returned

**The order fetch is two presses: the search pages are walked whole and counted by the status string TCGplayer gave each order, and only the statuses the operator ticks are detailed.** Built 2026-09-02, after the owner reported that the fetch had never worked once on the account it exists for. The refusal, verbatim: *"The LastThreeMonths range holds 370 orders and this fetch is capped at 100. Nothing was read rather than the first 100 being read and the rest silently left behind. Ask for a narrower range."* Code `order_too_many`.

**The cap was on the wrong quantity, and the remedy it printed could not be followed.** `server/order_transport.py` capped the ORDERS IN THE WINDOW at 100 to keep one press inside the only request budget anyone has a number for. A fetch is one search page per 25 orders plus one detail request per order, and `MAX_ORDERS` sized the whole of that against the 120 requests a minute the bridge extension holds itself to — a figure that is that client's own self-limit, read out of its source, and not a measurement of TCGplayer's server. The window's size is not what spends the budget: the pages are cheap and the details are the cost. And "ask for a narrower range" names a thing the transport cannot do — `Custom` needs a date pair whose query string was never captured, and the two ranges it knows are three months and two years.

### What the press measured

| | |
|---|---|
| orders in `LastThreeMonths`, this account, 2026-09-02 | **370** |
| the cap the fetch refused at | 100 |
| search pages to walk the whole window | 15 |
| requests for a full detail of the window | 385 |
| requests for the two orders awaiting shipment (D87's `Ready to Ship`) | 17 |
| times the one-press fetch had returned an order | **0** |

**The first row is the first real number this repo has about the order feed's size**, and it retires the "347 orders in 90 days" that `docs/specs/order-pipeline.md` §6 carried as an unverified external figure. The last row is the finding: a guard sized to protect the budget had made the route unusable on the one account it serves, and nothing in the tree could see that, because no test of `do_order_fetch` existed and no fixture holds 370 of anything.

### The status is the operator's and never the code's

**`fetch_open_orders`' own docstring ruled that "open" is the range and not a status filter, because the status vocabulary was never enumerated on the wire, and that ruling stands.** A string this module decided meant "still needs picking" would be a guess, and a guess that drops an order is an envelope that never ships. What changed is who chooses. `POST /orders/fetch {preview: true}` walks the summaries — `order_transport.summaries`, one request per 25 orders, no detail call — and answers the window counted by the status STRING each order carried, verbatim, with how many of each the ledger already holds at that status. The screen draws those strings as rows with tick boxes and nothing pre-ticked. `POST /orders/fetch {statuses: [...]}` details only the ticked ones, compared verbatim after a strip: never folded, never mapped, never a constant in code. The strings on the wire are the strings on the screen, and the operator ticks the two they are about to put in envelopes rather than the 280 that already shipped.

**The cap moved to the detail calls and it stays.** Fifteen pages plus a hundred details is 115 requests, inside the budget; a two-year window would not be, and its page count is what would reopen this. Past the cap the rest is COUNTED and answered as `remaining`, never silently left behind — `CLAUDE.md`'s rule against a silent drop is kept by making the drop loud and finite — and the next press picks it up, because `skip_known` hands the transport `{number: status}` as the ledger holds them and an order already detailed at this status is not detailed twice. An order whose status moved IS detailed again, which is how a shipped order's new word reaches the ledger without a full re-fetch. That map is `_known_orders`, read out of a store snapshot; the route still writes nothing.

**The transport does not sleep.** A route that paused its way through 370 details to stay under the budget would block one HTTP request for minutes, which is the wrong shape for a button and the shape D33 spawns a child for. Two presses inside one minute can pass the budget and nothing stops them; that is a cost named below rather than a cooldown, because the owner's ruling for this work was that the fetch stays a press and everything after it is what gets automated.

### What it costs

**Two presses where there was one, and a table to read between them.** The first press is the price of not guessing at the vocabulary. **The status strings are TCGplayer's, seen once.** The filter and the delta both compare the summary's `orderStatus` against the ledger's stored `status`, which came from the detail; if the two endpoints ever spell one state differently, `skip_known` re-details that order on every press. The preview would show the doubled string, so the operator would see it. **The `Custom` range is still not captured**, so the window is three months or two years and nothing between. **No cooldown**: the budget is the operator's to respect across presses. **And `detail` is still unexercised against the live host** — the summary walk is proven by the very refusal that opened this entry, and the projection of a buyer's name and address is proven against fixtures only. The first filtered fetch the owner presses is the measurement, and the transport's STATUS block says so.

**What would reopen this: a status spelled two ways between the summary and the detail, `Custom` captured off the wire, or orders arriving faster than a person presses.** The first is the delta re-detailing an order every press; the second gives the window a date and makes the status table smaller; the third is an unattended fetch, which is its own entry with its own argument about a cookie that expires under D53's supervisor with nobody watching the refusal.

## D92 — A bare `#` is the count, the key carries a sigil, and the check is what keeps them apart

**A bare `#` on an owner-side screen draws D58's count of the cards in a box, never the store key; a key is drawn only with the `B<box>` sigil D68 gave it.** Recorded and built 2026-09-02, after the owner reported the index on box 3 card 27 as wrong. It was not wrong. Box 3 was carrying two numbering systems and one sigil, and `#27` named two different cards on one screen.

**The two numbers are D58's and they are both correct.** `Place.index` is the store key — the `/inventory/<box>/<index>` path, the `<index>.jpg` the photograph is named after, what every write aims by. `Place.slot` is the number a person counts to, and it moves as cards leave the box in front of it. Both ride the wire because they answer different questions. What had never been decided is which one owns the `#`.

### What box 3 measured

| | |
|---|---|
| stored indices in box 3 (`RB Epics`) | 723 |
| cards on hand | 647 |
| departed — sold | **76** |
| index 27 | a sold `Astral Heron` |
| card 27 | index 63, `Master Yi, Unstoppable` |
| the two spaces at the top of the box | **76 apart** |
| on-hand cards in box 3 carrying no name, which is what made the row draw at all | 5 |

**Three renderers spelled both spaces `#`, on one screen.** `BoxBrowse.tsx`'s sticky header drew `Section 1 · #1–#82` from `section_start`/`section_end`, which are counts. `PlaceNeighbors.tsx` drew `#41` from `PlaceNeighbor.index`, which is a key. `join.departed_label` drew `B3 #27`, which is a key and says so. Only the third had ever argued its spelling.

### The sigil goes to the count, and D68 is not reopened

**`slot` is what a renderer draws and `index` is what a caller addresses with.** `_company` sends both per neighbour — the slot is the record's ordinal in `occupants`, which is already every on-hand index ascending, so it is `Position.slot` by the same bisect rather than a second derivation. `index` stays on the wire unread, because D45 makes a copies list a way back into the walk and a click target needs the key.

**D68's `B3 #27` is exempt BY NAME, and the exemption is the rule rather than a hole in it.** A departed card has no count — `Position.slot` answers null for one by design — so a key is the only number it has. The `B` is what marks it, which is D68's own argument, and it is why that form is not a bare `#`. The rule is therefore: **a bare `#` is a count; `B<box> #` is a key.**

**A FROZEN COUNT WAS PROPOSED AND MEASURED AND REJECTED ON THE MEASUREMENT.** The owner's first instinct was to give a departed card the count it held when it left, accepting that a historical number could collide with a live one. It collides essentially always: of 105 departed records across the store, **104 carry a number a live card in the same box holds right now**, and box 3 has 26 records sharing 18 numbers with each other. That is structural — any frozen count is by construction below the box's live card total, so a live card always holds it — and it is D68's own complaint (*"I'm seeing two box 1's"*) reproduced against live cards, which is the more dangerous direction, because a live card is one somebody walks to. **The frozen count survives as a FACT and not as an identifier**: it is worth drawing in the card panel, where nothing can mistake it for somewhere to reach, and that half is NOT BUILT — see the cost below.

### What is checked, and what the check cannot do

**`scripts/sigil-check.py` refuses a `#` composed from an expression naming `index`, on the commit path.** Narrow on purpose: it cannot tell a count from a key in general, and a check claiming to would be worse than none. What it catches is the one repeated mistake — reaching for the field called `index` when drawing a figure a hand is meant to count to.

**It found three sites nobody had looked at, on its first run.** `BoxOps.tsx`'s machine receipt naming skipped terminal rows, and `RunPanel.tsx` twice over a capture-directory preview. All three are legitimate — a departed record is in no slot, and `CropSample` carries no slot at all because nothing there has consulted the store — so each now carries a `sigil-ok:` marker with the reason. That is the check's real value: it did not find bugs in those three, it forced them to be *examined* rather than assumed. It also found a CSS class named `run-preview-slot` that had been drawing a key since it was written.

**Two prose statements of these facts were the exact reverse of the truth.** `types.ts` told every reader that the neighbour index "is a slot a hand can count to, not a store key". `t7_store_and_seams.py` told every reader that `Card 17` "IS THE SEVENTEENTH SLOT, NOT THE SEVENTEENTH CARD YOU CAN COUNT" — true when D30 wrote it, made false by D58 on 2026-08-30. `server.ts` had it right, as a recorded hazard, one screen away from `types.ts` having it backwards, and neither reader checked the other. **That is why this is a check and not a paragraph.**

### Two things this deleted, and one it fixed by accident

**The two stored `entry.label` writes are gone** — the mid-box delete's re-key and D83's move. Both composed a label in INDEX space while every route serves one re-rendered in count space by `_queue_row`; nothing read them, so no wrong number ever reached a screen. What they left was a field holding a plausible wrong rendering, indistinguishable from the correct ones `cli/resolve.py` writes, one forgotten `places` argument from being served. D56's rule already covers it: a rendering nobody can correct is joined at read time and not stored. The move was the worse of the two — the entry crosses INTO ANOTHER BOX, so the stale string named a section and card number from a different box's layout.

**`docs-audit.py`'s `commit path` row was matching flags across the whole hook file**, so adding a second self-testing check made `audit-self-test` — which D18 requires the hook not to run — report as being on the commit path. Its own comment already said what it meant (*"a check is on that path when the hook invokes its script IN ITS MODE"*); the match is per line now. A false positive there is worse than a loose one: it reports a check as gating commits when nothing runs it.

### What it costs

**The check is text, so a renamed local walks past it** — `const n = side.index` and then `#{n}` is invisible to it. A nominal type over the two numbers is the fix that could not be evaded, and it was rejected on blast radius: `slot` and `index` are plain numbers across the wire contract and forty call sites. The ceiling is in `docs/DEBTS.md` rather than left for someone to discover. **`PlaceNeighbor.index` is now sent and read by nothing**, which is a deliberate unread field and not an oversight. **And the departed card's frozen count is RECORDED AND NOT BUILT**: it needs the event log, because current state plus `state_at` does not reconstruct it — tested, and 31 of 105 records come out wrong that way, box 1 uniformly by one (a sale that was later undone) and box 3 indices 37–39 in both directions (a reindex). That makes it a route on `getPriceHistory`'s shape, and it carries a semantic question nobody has answered: what a re-sold card's frozen count means.

**What would reopen this: a neighbour row that becomes a click target, a screen that needs to draw a key inside a count column, or the frozen-count panel.** The first is why `index` is still on the wire. The second is what `sigil-ok:` is for. The third is the one piece of this entry that is a want rather than a build.

## D93 — The copies panel is the picker, and a full line refuses the take

**Which copies of a line go in the envelope is CHOSEN off the copies panel, one press per copy, in any box.** Built 2026-09-02 on the owner's complaint: *"When I have an order of 2 cards and I have inventory for 3, I basically should be able to pick which two I sell, instead currently it's like predetermined, and using the 'take this one instead' system is not intuitive it should be done differently."*

**This is D90's own third reopening condition, taken.** That entry closed with *"`SearchCopy` gaining a `capture_id`. Today a copy is swapped in only by walking to it, because the aim needs an id the search rows do not carry. If they carried one, an unpicked copy could be taken straight off the panel without the walk moving — worth arguing rather than taking, because the walk-to IS the flow: you look at the card before you swap it in."* The argument came back the other way from the person doing the walking, and the flow it defended is what they called unintuitive.

### What was actually in the way, and it was one field

**`resolve_all` decides which copies fill a line before anybody reaches a drawer, and that half is right and unchanged.** It allocates over the WHOLE open set in one pass so two envelopes cannot name one card, and the operator wanting a different copy of the same SKU is not a defect in that allocation — it is a fact about which cards are in their hand.

**What made the correction awkward was that a copy could not be AIMED at.** Every write in the walk aims by `capture_id`, checked against the card actually at the slot (`capture_id_mismatch`, D90) — and `GET /search` did not send one, so the only aimable copies were the resolver's own picks and whichever card the walk was standing on. Hence the two-press errand the owner objected to: walk to the copy, then press `Take this one instead`, which replaced the stop's first target one copy at a time.

**The carve-out this reopens is narrower than it read.** `app/src/types.ts:SearchCopy` refused `confidence` and `capture_id` together, to stop *"a second inventory view growing inside a search result"*. That rule stands for the metadata; it never had an argument about the identity. **An identity is not a view.** `_copy_row` sends `capture_id` now, null on a record written before ids were kept — and a copy carrying null says `no capture id` where its control would be, rather than offering a press the server would refuse.

### A full line refuses the take, and the ring was the alternative

**Told that the panel would be the picker, the owner was asked what a third tap should do when the line already has the two copies it is owed, and chose the refusal.** At `2 of 2` every other row draws the count where its control would be; dropping one is what makes room.

**The alternative was a ring, and it is the one this build would have shipped unasked.** Tapping a third copy would drop the longest-standing take — one press per correction, and because the resolver's picks are always the oldest members, tapping exactly the copies in your hand converges on exactly those. It was declined on the property that makes it convenient: **nothing may leave the envelope on a press aimed at something else.** A row that un-takes itself because a different row was pressed is a change the finger did not make, to a list whose whole job is to say what is in the operator's hand.

**What it costs is the second press, and it is named rather than hidden.** A swap is `Don't take` then `Take`, and the panel says so in one sentence.

### One map, not two, and an empty list is an answer

**`retargets` and `excluded` collapse into `chosen`.** They existed because the gesture was a CORRECTION: a replacement list for the copy swapped in, and a set of capture ids the operator had said were not in the drawer. A picker has one fact per stop — the copies taken — so there is one map, keyed by stop, and `targetsOf` reads it with `??` rather than `||`: a stop the operator has emptied stays empty instead of falling back to the picks it was seeded from. *"None of these"* is a thing that can now be said.

**The vocabulary follows the gesture.** `taking` in ink and `not taking` in muted, `Take` and `Don't take` on the rows, `2 of 2 taken` where a full line refuses, and `take 2 of 2` on the banner — a bare numerator answered "is this line full" only for somebody who remembered what the buyer asked for. `Not here`, `Back in` and `taken instead` are gone.

### The walk follows a drop and not a take

**Taking a copy appends it, so the walk stands still.** The landing is the stop's first target; a copy pushed to the FRONT — which is what the swap did, deliberately, so the stop followed the operator to the drawer they had walked to — would now jump the screen to whatever row was just ticked, and under the refusal above a swap is two presses, so it would move the walk twice for one correction.

**Dropping the copy the walk is standing on DOES move it**, to the next copy the envelope is taking, in another box if that is where it is. That is the errand D90 built the landing for, and it is the half worth keeping: the walk goes where the cards are, not where the taps are.

### The two shortfalls survive, and the order of derivation is what keeps them honest

**`short` is copies the resolver never found and `not taken` is copies it found that the operator has not put in the envelope** — the ledger's problem and the shelf's, and one number covering both sends a person to the wrong place. `Stop.available` is the count of aimable picks; what is missing is `owed - take`; as much of that as a pick could still answer for is `not taken`, and the rest is `short`.

**Derived in that order rather than as two independent counts, which is what stops them double-counting.** A copy taken that the resolver never offered — a free copy in another drawer — closes the gap rather than being counted against it, and the old subtraction (`all picks` minus `kept picks`) could not express that at all, because a hand-taken copy was not in either list.

### What did not move

**The resolver's picks are still the default, and that is what keeps the common case free.** A line owed two with two copies on the shelf is zero presses; the picker costs a press only where the operator has an opinion about which copies. Nothing about the envelope moved either: one press per order, one transaction, `Mark sold` hidden on every row while an order drives (D90's seam), `Retire` still offered.

**A copy another stop has been allocated is still refused, and still by the allocation rather than by the drawer** (D7, and the owner's *"You're giving boxes too much independence"*). The mark says `for order N` beside the missing control. A pooled copy (D24) is refused too: it is a count rather than a location, so there is no slot for the aim check to check against.

### What it costs

**The choice is still this screen's and this session's.** `chosen` is React state; a reload drops it and the envelope falls back to the resolver's picks with nothing on screen saying it changed. That is D90's cost unchanged, and the case for storing it is no stronger now — a take is a statement about the next press, not a fact about the store.

**A line the resolver could not answer at all is still not walkable.** `stopsOf` keeps a line with no aimable pick out of the queue, so the picker cannot be used to fill one by hand. No reachable gap follows from it today — the copies that would fill such a line are pooled, id-less, or held by another order, and all three are refused on their own terms — but the queue's membership is now decided by a narrower question than the panel can answer.

**The take is per stop, and the panel draws one SKU.** In wave mode each stop keeps its own list, which is right; what it means is that no screen shows the whole envelope's copies at once, and the banner's counts are what stands in.

**And it is still built over an ingest no real order has been through.** D90's table is unchanged: 0 orders in the ledger, 0 copies ever recorded as pulled for one. Every guarantee here is proven by `app/tests/order-walk.spec.ts` and by nothing that has held a buyer's money.

**What would reopen this.** *A second pair of hands*, exactly as D90 has it — two people walking one wave each hold a `chosen` the other has already spent. *A line the resolver answered short while a copy sat takeable in the panel*, which would mean the queue's membership test and the picker disagree about what is fillable. *A tap that costs a card* — the refusal above is a bet that a change the finger did not make is worse than a second press, and the measurement that settles it is an operator swapping copies at a real drawer.
