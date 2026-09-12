## D137 — The catalog is Near Mint by rule, because it was only ever Near Mint by accident of the file

**Settled 2026-09-11, from the owner asking where a feature had gone.** *"how come on
review/pricing in the runs, ive somehow lost the ability to fast forward through the review
by just stating all were near mint?"* — and then, when the first account of it was wrong,
the correction that located it: *"I've never once been asked to judge the condition of cards
in a review queue until today. They always were just pre-assumed to be Near Mint."*

They were pre-assumed. That is the whole finding.
**D12 hardcodes Near Mint and nothing in this tree had ever enforced it on the catalog.**
`pipeline/join.py:Catalog.from_export` has
been touched once since it was written (2026-08-23, when games became data) and has never
carried a `Condition` predicate. Every rung of `variant.resolve` resolves to a Near Mint
string, so the *ladder* was never in doubt — but the candidate list a queue entry carries is
`found.rows`, straight off the export, ungated. The catalog was narrow because the operator
was producing narrow files by hand.

### What changed was the input, and the date is exact

D65 (2026-08-30, `fb516df`) built the automatic fetch. `Scope.condition_ids` was declared in
that commit, has never been populated by any caller since — one commit in the whole history
touches that name — and `Scope.model`'s `ids()` turns `()` into `["0"]`, the portal's *All
Conditions*. On **2026-09-01** every run was re-joined against fetched exports, including
`2026-08-24-box2-01`, whose original hand-downloaded CSV is still sitting unused beside the
file its manifest now names.

| run | export | grades |
|---|---|---|
| `2026-08-29-box1` … `2026-08-31-box3` | hand-downloaded | 2 conditions, **0 played** |
| `2026-09-01-box3/4/5` onward | fetched | 11 conditions, **8,032 played** |

**And the experience changed ten days after the mechanism did.**
Counted off the store's own `answered` events, the operator has
answered **8** grade-bearing questions against a wide export in total, all on 2026-09-01, out
of 240 answers; on 2026-09-11 it was **108 of 131**. Before that the work was
`number_unread_name_matched` — one candidate, one press — and the handful of `set_ambiguous`
cards were 2-row choices between two *sets*, both Near Mint. A session telling the operator
they had had this since the 1st was reading a mechanism as an experience.

### Three costs, and only one of them is the one that was reported

**The group press stopped qualifying.** D29 requires every card in the worklist to offer
exactly one candidate. Nothing in `app/src/ReviewQueue.tsx` changed — `groupOffer` was
byte-identical to its pre-Banchi self and `G` is still the key.

**AND THE LAST SENTENCE OF THIS PARAGRAPH WAS WRONG, CORRECTED 2026-09-11.** It read: *"With
five grades per finish no entry can ever carry one row, so the control correctly never
draws."* The premise does not hold and the conclusion was never the reason. Counted off the
store's own queue files: of the 141 `rarity_claim_mismatch` entries box 1 wrote that day,
**139 carried exactly one row** — the grades never reached them, because D23's rarity filter
runs before the candidate list is built and cut every row the claim excluded. In the parked
queue alone, **99 of 101** entries offered one row of one condition. The press did not draw
for them, and the reason was `groupOffer`'s ALL-OR-NOTHING shape: the two entries that
carried two rows returned null for the other ninety-nine. Ninety-nine cards were answered one
press at a time because two of their neighbours were ambiguous.

That is fixed rather than merely recorded: the offer is the largest cluster anchored on the
card on screen, and the confirm panel says how many it is leaving behind. A wide export still
narrows what qualifies — the paragraph's subject is real — but "correctly never draws" was a
defect wearing a ruling's clothes.

**D3 rung 2 died outright, and that is the larger cost.** `CATALOG_FORCED` fires on
`len(candidates) == 1`. Measured on the owner's 2026-09-11 Riftbound export: **0 of 1,246**
numbers held a single row as fetched; **629** do once the grades are gone. Replaying that
day's 122 queued cards through the narrowed rows,
**50 would never have been queued at all** — 32 `detected_finish_not_stocked`, 17
`ambiguous_no_signal`, 1
`rarity_claim_mismatch` — and the 57 `set_ambiguous` that remain offer 3 rows rather than 15.
Rows offered per card across that queue: **8.6 → 1.8**.

**A mis-tap was listable.** `_answer_target` validated that the answer matched the row
*offered* and never that the row should have been offered. Answering `Damaged Foil` would
have written that SKU, and `join_batch` rung 0 re-finds an answered row by its own condition
string, so the wrong grade would have travelled into the import file. Nothing went wrong:
all 1,967 conditioned card records in the store read `Near Mint` or `Near Mint Foil`.

### The rule lives in the join, not on the wire

`Catalog.from_export` keeps a row whose `Condition` is one of the game's own
`condition_by_finish` values — read off the registry, as
`server/capture_server.py:_near_mint_conditions` already reads it — plus
`tcgcsv.SEALED_CONDITION`. `cli/cmd_join.py` reports the two drops separately, because
"8,077 row(s) of other product lines dropped" would have been false and a number nobody can
account for is a number the next person deletes the filter to explain.

**`ConditionIds` stays unpopulated and `STANDING_FILTERS` does not grow.** This is D76's last
paragraph amended rather than repealed, and the amendment is narrow: that paragraph left the
condition axis unspent citing D64's finding that "a condition filter thins a number's rows and
D3 rung 2 then decides a card from whichever row survived" — which is D64's measurement of the
**printing** axis, not the condition one. D64 itself says so in as many words two sections
earlier: *"Play conditions are not finishes… all 153 numbers read as thinned and not one had
lost a finish."* Re-measured here on the owner's own export:
**0 of 1,246 numbers lose a finish**, because each finish keeps its own Near Mint row.
The rarity axis stays unspent for
its own separate reason, untouched.

Given that, the fetch could safely narrow too — and deliberately does not. The rule belongs
where it cannot depend again on how the CSV was produced, which is the exact dependency that
broke on 2026-09-01; a hand-downloaded or re-used wide file must join correctly. Leaving the
wire wide also keeps the filter's subject present in every real export rather than in
fixtures alone.

### Sealed product survives, and it is not an exception

Booster displays, bundles, blisters and event kits carry `Unopened`:
**one row per product, never a sibling, no `Number` at all**, so they live only in
`Catalog._blank_number_by_name`
and cannot change what any numbered card resolves to. Measured across both wide fixtures,
**zero sealed `Product Name` cells collide with a single's**, exact or folded, so keeping
them cannot put a Booster Box on a card. Riftbound's own export prices an Origins Booster
Display at $250.78. The owner's call, and the measurement makes it free rather than a
judgement: *"idk if you needed to drop sealed items"* — it did not.

A play grade is a second reading of a card this product sells at one grade. `Unopened` is the
only condition its product is ever listed in. They are not the same kind of cell, which is why
the rule is "drop the play grades" rather than "keep only Near Mint".

### What the guard had to be, because the old one could not see this

**T3's `SOURCE_FIXTURE` is `sv09_export_untouched.csv`, which is Near-Mint-only.** Its whole
`from_export` block passes identically with the filter present and absent, and was green
through all ten days. `_check_condition_scope` runs against the two **wide** fixtures instead
— Riftbound 10,078 rows over 11 conditions, Pokemon 7,802 over 16 — and begins by asserting
they really are wide, because without that every assertion under it passes by accident.

Mutation-tested in three arms, each killed by a different assertion and no assertion
redundant: the predicate deleted (rung 2 and the play-grade and refusal checks go red), sealed
dropped from the keep set (only the four sealed checks), and the set narrowed to one condition
so a foil finish is thinned (only the finish-preservation check — D64's real worry, caught).

**The first draft of the rung-2 assertion survived arm 1 and had to be rewritten.** It counted
distinct *finishes* per number, and a set of finishes collapses the exact multiplicity the bug
was made of: five grades of one finish is one finish and five candidates. Rung 2 is
`len(candidates) == 1` over **rows**. It counts rows now and resolves one through the real
ladder, because a count is not a resolution.

### Not the whole of what made 2026-09-11 hurt

Box 4 was captured with **no set hint on 448 of its 464 cards**, where boxes 5 and 6 are 100%
`Unleashed`. 178 of the 1,246 Riftbound numbers collide across sets, and an unhinted collision
goes straight to `set_ambiguous` (D65/D76 rung 4). That is the other factor, it is an
operating fact rather than a defect, and it is named here so this entry is not read as having
cured it: the 57 `set_ambiguous` cards left after this change are the ones a set hint would
have answered.

### Deliberately not done

**The live queue is not repaired by this change and no command was run against the store.**
`Queue.upsert` replaces an open entry wholesale and `Queue.release` drops one that no longer
belongs, so the next join of a run rewrites its entries and the stale ones self-heal.
`_answer_target`'s new `condition_not_listed` refusal is the floor under the entries written
before this landed — unreachable from the screen once a run is re-joined, which is the point.

**`scripts/demo-seed.py:export_variants` has the same defect, left alone on the owner's word.**
It groups the raw fixtures by `Product Name`, so the published demo can offer
10,452 played rows as review candidates. Recorded, not fixed.

