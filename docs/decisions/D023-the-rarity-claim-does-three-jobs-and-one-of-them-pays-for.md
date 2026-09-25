## D23 — The rarity claim does three jobs, and one of them pays for the feature

The capture screen gains a multi-select rarity claim, scoped by the chosen game. It does three things, and they are listed in order of what they are worth.

**1. Cross-check — the new `rarity_claim_mismatch` review reason.** Emitted in the **variant ladder**, not in routing: routing answers *"is this trusted enough to list?"* and the ladder answers *"which row is this?"*, and routing is currently the only pipeline module with no Pokémon in it. It filters the candidate rows to the claimed rarities and reviews when nothing survives — filter-then-contradict, because on a multi-set collision the filter breaks a `duplicate_condition` tie for free.

**This is the job that pays.** T1's recorded misses are `051/197` for `031/197` and `271/167` for `211/167` — *confident* answers, name right, digits wrong. No confidence threshold fires on those. A rarity contradiction does.

**Rung 0 must not consult it.** A human who looked at the photograph beside the candidate rows outranks a claim about the stack it came from. `answered()` already refuses to re-consult metadata and detection, and the failure that taught it is on the record: sixteen answered cards re-deriving their disagreement and re-parking on every join.

**2. Narrow the finish chips.** Offered = the **union** of `finish_by_rarity` over the claimed rarities — union, not intersection, because a Common+Rare stack legitimately holds both plain-NM Commons and holo Rares. Three rules, each of which exists to stop a specific harm:

- **An empty rarity claim narrows nothing.** The screen behaves exactly as it does today. This is the compatibility guarantee that makes the whole feature strictly additive.
- **It never auto-selects, not even when one finish is left.** A claim of `{Double Rare}` leaves only `holo` and the control still rests on `no claim`. Ladder rung 2 (`CATALOG_FORCED`) already resolves a holo-only Double Rare for free, and a manufactured claim makes rung 2 unreachable for every card this rig sees.
- **Excluded chips are rendered and unselectable, not hidden**, so the operator can see what the claim cost them and take it back by clearing the rarity.

**3. Prompt injection — MEASURED AND SWITCHED OFF (2026-08-23).** Built in the user turn because it is per-card, scoped so it could not poison D3 rung 3, pinned under its own `rarity_fingerprint` so the scored default never moved — and then measured with best-case claims for $0.17, where it lost on every watched axis: holdout down 1.5 points, high-confidence misses up two, and the finish distribution hardened against the carve-out sentence itself. the gates corpus's `T1` entry carries the numbers; the switch in `cli/cmd_identify.py` cites them and names the re-enable condition (a rig-photo measurement, `PKMNSCAN_T1_RARITY=1`). Jobs 1 and 2 are what this entry now rests on, which is where it always put the weight.

The original design, kept because the machinery still exists behind the switch: `SYSTEM_PROMPT` already says *"Do not infer the finish from the card's rarity"*, and a careless clause makes it do exactly that — poisoning the one signal that catches a mis-sorted card. Gated behind `PKMNSCAN_T1_RARITY=1` for an A/B, the same shape as the set-hint knob, and **shipped in its own step** so the fingerprint moves once, deliberately, with a re-measured T1.

**The superset rule is what makes unselectable safe, and the two must never be separated.** `finish_by_rarity` is authored as a superset of what any one export proves. SV09 stocks no plain Near Mint `Rare`; a matrix derived from that observation alone would make a legitimate plain-NM `Rare` stack **unclaimable**, and with the chip unselectable the operator would have no way to say what is true. The audit enforces the superset direction — it blocks on an observed pair the matrix is missing and only asks about the excess. **If anyone ever narrows the matrix to one export's observations, unselectable becomes a trap.**

## Amendment, 2026-09-24 — a fourth job: rank what is offered

**The claim used to only refuse and narrow.** It never reordered a candidate list. `4/383` on the owner's real store is the case. It read `Calm Rune` / `R02`. Capture claimed `Showcase`.

The number found five `R02` Commons across three sets. That is a `set_ambiguous` collision. It queues with no claim check at all, because that rung fires in `Catalog.candidates`, before `variant.resolve` ever runs. Three `Calm Rune (R02a)` Showcase rows answer to the claim. They sat under a different number. The same NAME also answers to that number. The entry's suggestions never offered one of them. `GET /review/4/383/catalog?q=Calm%20Rune` found all sixteen `Calm Rune` rows. It returned nine, in catalog order. The Showcase rows sat in the tail, not the front.

**The owner's ruling, on the suggestions (2026-09-24):** if both do not match even after that, the card can come for review. In review it should offer a name-match option, a number-match option, or both.

D253 already built the name-match half of this, for a DISPUTED name (D146's `name_disputes`). `4/383`'s name was never disputed. The `R02` Commons carry the name `Calm Rune` too, so `name_disputes` stays silent. The rung that queues it, `set_ambiguous`, never asks the ladder at all. This amendment closes that gap: a card whose number found real rows, under a real name, but whose RARITY the claim rejects.

**4. Rank — job (c), added this entry.** `pipeline/join.py:rank_by_claims` scores each candidate row. The score counts how many capture claims it agrees with: rarity, finish (`metadata_finish`), set hint. It orders the list best first.

This is presentation only. It cannot add a row that answers to nothing. It cannot pick one on its own. A card whose evidence favours no row is left tied, exactly as it arrived. Nothing here chooses for the operator.

`join_batch` widens `found.rows` by name first, over `catalog.rows_for_name`. It fires whenever the number's own rows never satisfy a present rarity claim. `rank_by_claims` then puts every claim-agreeing row in front, named or numbered. That is what earns a claim-matching row its keyboard digit (`app/src/ReviewQueue.tsx`'s `MAX_KEYED_CANDIDATES`).

`server/capture_server.py:do_review_catalog`'s free-text search calls the SAME function. A claim scores once, for both the pipeline's own suggestions and a typed search.

**Rung 0 stays exempt, unamended.** D146's own rule holds: *"a human who looked at the photograph beside the candidate rows outranks a claim about the stack it came from."* This holds by construction, not by a new check. A `HUMAN_ANSWERED` card resolves to one row before any candidate list is built. Ranking a list of one is always a no-op.

**The cutoff this widening exposed is recorded in `docs/specs/card-variants.md`.** Section 3c already reasoned about `4/383` and its nine-row limit. The owner's ruling on that limit, and the search's own before and after, are recorded there.
