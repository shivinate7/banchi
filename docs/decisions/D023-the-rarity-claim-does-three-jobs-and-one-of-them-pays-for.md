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
