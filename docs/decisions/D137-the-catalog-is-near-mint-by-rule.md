## D137 — The catalog is Near Mint by rule

**Ruling: the join keeps only Near Mint and sealed rows of the catalog.** Play grades are dropped in the join, not on the wire.

Settled from the owner asking where a feature had gone. The owner could no longer fast-forward the review queue by stating that every card was Near Mint. The owner corrected the first account: until that day the owner had never been asked to judge a card's condition in the review queue. Conditions were always pre-assumed Near Mint.

D12 hardcodes Near Mint. Nothing in the tree enforced it on the catalog. `pipeline/join.py:Catalog.from_export` never carried a `Condition` predicate. Every rung of `variant.resolve` resolves to a Near Mint string, so the ladder was never in doubt. The candidate list a queue entry carries is `found.rows`, straight off the export, ungated. The catalog looked narrow only because the operator produced narrow files by hand.

### What changed was the input

D65 built the automatic fetch. `Scope.condition_ids` was declared in that change. No caller has populated it since. `Scope.model`'s `ids()` turns `()` into `["0"]`, the portal's "All Conditions". After that change, every run was re-joined against fetched exports, including `2026-08-24-box2-01`, whose hand-downloaded CSV still sits unused beside the file its manifest now names.

| run | export | grades |
|---|---|---|
| `2026-08-29-box1` … `2026-08-31-box3` | hand-downloaded | 2 conditions, **0 played** |
| `2026-09-01-box3/4/5` onward | fetched | 11 conditions, **8,032 played** |

The operator's experience changed ten days after the mechanism did. The store's `answered` events show 8 grade-bearing questions against a wide export, all on the re-join day, out of 240 answers. Later it was 108 of 131. Before that, the work was `number_unread_name_matched`: one candidate, one press. The few `set_ambiguous` cards were two-row choices between two sets, both Near Mint. A session that said the operator had this since the re-join read a mechanism as an experience.

### Three costs

**The group press stopped qualifying.** D29 requires every card in the worklist to offer exactly one candidate. `groupOffer` in `app/src/ReviewQueue.tsx` did not change. Of the 141 `rarity_claim_mismatch` entries box 1 wrote that day, 139 carried exactly one row. D23's rarity filter runs before the candidate list is built. It cut every row the claim excluded. In the parked queue alone, 99 of 101 entries offered one row of one condition. The press did not draw for them. `groupOffer` is all-or-nothing: two entries with two rows returned null for the other 99.

Fixed. The offer is now the largest cluster anchored on the card on screen. The confirm panel says how many cards it leaves behind. A wide export still narrows what qualifies. "Correctly never draws" was a defect that looked like a ruling.

**D3 rung 2 stopped firing.** `CATALOG_FORCED` fires on `len(candidates) == 1`. On the owner's Riftbound export, 0 of 1,246 numbers held a single row as fetched. With the grades gone, 629 do. Replaying that day's 122 queued cards through the narrowed rows: 50 would never have been queued. Of those, 32 were `detected_finish_not_stocked`, 17 `ambiguous_no_signal` and 1 `rarity_claim_mismatch`. The 57 remaining `set_ambiguous` cards offer 3 rows, not 15. Rows offered per card across the queue fell from 8.6 to 1.8.

**A mis-tap was listable.** `_answer_target` checked that an answer matched a row offered, and never that the row should have been offered. Answering `Damaged Foil` would have written that SKU. `join_batch` rung 0 re-finds an answered row by its own condition string, so the wrong grade would have reached the import file. It did not happen. All 1,967 conditioned card records in the store read `Near Mint` or `Near Mint Foil`. `_answer_target` now refuses a row the join would not offer.

### The rule lives in the join, not on the wire

`Catalog.from_export` keeps a row when its `Condition` is one of the game's `condition_by_finish` values. The registry supplies those, as `server/capture_server.py:_near_mint_conditions` already reads them. It also keeps `tcgcsv.SEALED_CONDITION`. `cli/cmd_join.py` reports the two drops separately. A line reading "8,077 row(s) of other product lines dropped" would be false, and an unexplained number is one the next person deletes the filter to explain.

`ConditionIds` stays unpopulated, and `STANDING_FILTERS` does not grow. This amends D76's last paragraph, narrowly. That paragraph left the condition axis unspent, citing D65's finding that a condition filter thins a number's rows. D65 measured the printing axis, not the condition axis. D65 says so: "Play conditions are not finishes… all 153 numbers read as thinned and not one had lost a finish." On the owner's export, 0 of 1,246 numbers lose a finish, because each finish keeps its own Near Mint row. The rarity axis stays unspent for its own separate reason.

The fetch could narrow too, and deliberately does not. The rule belongs where it cannot depend on how the CSV was produced. That dependency broke at the re-join. A hand-downloaded or reused wide file must join correctly. Leaving the wire wide also keeps the filter's subject present in every real export, not only in fixtures.

### Sealed product survives

Booster displays, bundles, blisters and event kits carry `Unopened`. Each is one row per product, with no `Number`. They live only in `Catalog._blank_number_by_name`, so they cannot change what a numbered card resolves to. Across both wide fixtures, zero sealed `Product Name` cells collide with a single's, exact or folded. Keeping them cannot put a Booster Box on a card. Riftbound's export prices an Origins Booster Display at $250.78. Keeping sealed product is the owner's call. The measurement shows the sealed items did not need dropping.

A play grade is a second reading of a card this product sells at one grade. `Unopened` is the only condition its product is listed in. The two are different kinds of cell. That is why the rule is "drop the play grades", not "keep only Near Mint".

### The guard

T3's `SOURCE_FIXTURE` is `sv09_export_untouched.csv`, which holds Near Mint rows only. Its `from_export` block passes with the filter present and absent. It stayed green through the whole change. `_check_condition_scope` runs on the two wide fixtures instead: Riftbound at 10,078 rows over 11 conditions, and Pokemon at 7,802 rows over 16. It first asserts that they are wide. Without that assertion, every check under it would pass by accident.

Three mutation arms, each killed by a different assertion:

- The predicate deleted: rung 2, the play-grade checks and the refusal checks go red.
- Sealed dropped from the keep set: only the four sealed checks go red.
- The set narrowed to one condition, so a foil finish is thinned: only the finish-preservation check goes red. That is D65's real worry, caught.

The first draft of the rung-2 assertion survived arm 1. It counted distinct finishes per number. A set of finishes collapses the multiplicity the bug was made of. Five grades of one finish is one finish and five candidates. Rung 2 is `len(candidates) == 1` over rows. The assertion now counts rows, and resolves one through the real ladder, because a count is not a resolution.

### What else made the re-join day hurt

Box 4 was captured with no set hint on 448 of its 464 cards. Boxes 5 and 6 are 100% `Unleashed`. 178 of the 1,246 Riftbound numbers collide across sets. An unhinted collision goes straight to `set_ambiguous` (D65 and D76 rung 4). This is an operating fact, not a defect. It is named here so this entry is not read as having cured it. The 57 `set_ambiguous` cards left after this change are the ones a set hint would answer.

### Deliberately not done

- **The live queue is not repaired.** No command ran against the store. `Queue.upsert` replaces an open entry wholesale. `Queue.release` drops one that no longer belongs. The next join of a run rewrites its entries, so stale ones heal. The new `condition_not_listed` refusal in `_answer_target` is the floor under entries written before this change. The screen cannot reach it once a run is re-joined.
- **`scripts/demo-seed.py:export_variants` has the same defect.** It groups raw fixtures by `Product Name`, so the published demo can offer 10,452 played rows as review candidates. Recorded, not fixed, on the owner's word.
