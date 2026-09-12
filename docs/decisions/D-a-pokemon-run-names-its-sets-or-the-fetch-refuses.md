## D-a-pokemon-run-names-its-sets-or-the-fetch-refuses — A widening is safe only while the category fits, and Pokemon's does not

**A game whose whole category cannot be fetched may not have that fetch chosen for it by cards that said nothing.** Built 2026-09-12, on the owner's ruling.

Three options were put to the owner about the Pokemon catalogue fetch sitting at 97.24% of `tcg_export.MAX_BYTES`: refuse early under the cap, leave it visible, or fix the cause. They chose the third, in those words — *"make unhinted Pokémon cards impossible."*

### The measurement, and what it is not

**One forced whole-category Pokemon fetch, 2026-09-12: 32,629,598 B over 222,849 rows.** That is 97.24% of the 33,554,432 B ceiling the download is refused past, 903 KB of headroom, against 238,482 B for the one set the owner's Pokemon cards all name. The widening is 137x and it lands two per cent short of a refusal.

**D76 wrote that a widening is always safe. For this category it is 903 KB from a refusal.** That sentence is the whole of this entry: "safe" was never wrong in principle, it was unbounded, and one category has now been measured past the point where it holds.

**ONE unhinted card is all it takes, and that is D76's own rule working correctly.** A set filter is legal only where every card of the game is hinted and every hint resolves, because a hint is evidence about the card that carries it. So the box stops being unanimous the moment one card says nothing, and the fetch goes from 238 KB to 32.6 MB.

**THIS IS PREVENTIVE AND NOTHING WAS BROKEN.** Measured on the owner's live store the same day: 543 Pokemon cards, 543 of them carrying `ME01`, zero unhinted. Riftbound holds 700 unhinted of 1,992 and that costs nothing — its `export_scope` is `category`, so its whole 10,078-row catalogue comes down in one file however its cards are labelled. The 97.24% figure came from a fetch made to measure the cliff, not from anything this store does.

### Where it is enforced, and why not the other three places

**`server/pipeline_routes.py:_scope_for_run`, the one function that decides how wide to ask.** It is called by the press-nothing preview and by the paid fetch, so one refusal gets two behaviours for free: `GET /pipeline/runs/<name>/scope` DRAWS it, because that route already reads a `PipelineRefusal` as data, and `POST .../export` refuses 409 without opening a socket. The operator therefore meets this before the money gate, on the screen D76 built for exactly that.

**NOT THE SHUTTER, AND THIS IS THE LOAD-BEARING REJECTION.** `app/src/setHint.ts`'s own header carries D65's rule — it judges, it never refuses, because the rig does not stop for an autocomplete at a 623 ms feeder cadence. A capture refused mid-feeder is worse than an unhinted card: it leaves a physical card in the drawer with no record, which renumbers every card behind it. An unhinted card is repairable; a missing record is a box whose contents and store disagree.

**NOT A CAPTURE-TIME PRECONDITION EITHER.** Refusing to arm without a hint would close the future and do nothing about any card already captured, and a client-side gate is not a boundary — the CLI, a stale tab and `requeue` all reach the store.

**NOT `#/review`.** Its `ANSWER_FIELDS` are `sku`, `condition`, `undo` and `from_catalog`. Answering a queued question picks a SKU; it cannot write a claim, so it is not where a missing hint gets fixed.

**The cliff is a property of a REQUEST, not of a card**, which is the general form of all three rejections. No number of unhinted cards costs anything until something asks TCGplayer for a catalogue, and the place that decides the width of that request is the only place that knows the game, the counts, the unresolved hints and the measured bytes at once. Anything earlier has to guess.

### The rule is a per-game field, because the cliff is not

**`export_needs_hint` in `pipeline/games.py`, with `export_category_bytes` beside it as its evidence.** The same shape `export_scope` already uses: a claim that has to be measured, authored only where the measurement exists, and false by omission.

**It is NOT derived from `export_scope`, and three of the four catalogued entries are why.** `sets` is the default and is carried by `pokemon_code` and `one_piece` as well. A predicate off `export_scope` would refuse both for a measurement neither has.

**`pokemon_code` SHARES CATEGORY 3 AND IS DELIBERATELY EXEMPT.** It sits on the same 32.6 MB cliff, and it joins by `name_only` — the blank-`Number` rows — so a set filter buys the match nothing, and a code card does not reliably print a set for the operator to read off. A hint demanded there is friction with no narrowing at the end of it, which is the argument `riftbound` wins its `category` on. **A hint is refusable only where a hint would have narrowed the fetch.**

**So the cliff stays reachable on the code-card track, and that is a named gap rather than an oversight.** What covers it is what covered it before: the width is drawn on the preview before the press, and `_too_large_sentence` says the scope is why if the download is ever refused. Closing it needs a narrower transport — a paged or streamed fetch — not a claim the operator cannot make.

**`export_needs_hint` may not be `False` where it would be a lie, and may not be authored where it could never fire.** `scripts/docs-audit.py`'s `games registry` row refuses the boolean on an entry naming no `export_category_bytes`, on one naming no `tcgplayer_category_id`, and on one whose `export_scope` is `category` — that last would be a rule that can never run, since such a game widens by policy and never reaches the cards.

### `chosen_by == "cards"` is the whole predicate, and nothing is ever stranded

**The refusal fires only where the CARDS under-specified the scope** — `no_hints`, `partial_hints`, `unresolved_hints`, `no_hints_resolved`, the four branches that set `chosen_by` to `cards` and the only four.

**D76's other two voices pass straight through.** An operator sending `set_ids` or `scope: category` is `operator` and is not refused, which is both the override and the reason a refused run is never a stranded one: it exists to stop the machine widening on a guess, not to stop a person. A game whose own `export_scope` is `category` is `policy` and never reaches the question.

**And the cards themselves are repairable, through a path that already existed.** `PUT /inventory/<box>` takes `set_hint` over a whole box or a named selection in one transactional write — the owner asked for it by name on 2026-08-23, *"if i accidentally didn't do it at the capture level, i'd like to be able to do it retroactively"* — and it is reached from `#/inventory` → Manage box → Set claims, with the card-level `PUT /inventory/<box>/<index>` beside it. **No second repair path was built**, and the refusal names that screen rather than describing a capability.

### The screen says it at the rig, where it is still free

**The capture screen draws a note and refuses nothing.** `GameEntry.export_needs_hint` reaches the app because `GET /games` serves the registry verbatim, so the boolean an operator meets is the same literal the fetch refuses on and there is no second threshold to drift. The field's head reads `Needed for this game` instead of `Optional`, the meta beside the cursor reads `needed`, the note names the refusal and the screen that fixes it, and the resting row says so too — which is the state the screen sits in for every card of a sitting nobody pressed `H` on, where a bare `None` reads as a choice that was made.

**Without that note the operator's first knowledge of the rule would be `#/runs`, an hour of captures later** — which is the exact defect `setHint.ts` was built to end, and building the refusal without it would have reintroduced it one register up.

### What proves it

**Both directions, on the same cards, with one flag between them.** T7 asserts the refusal FIRES on a bare Pokemon run and on a partial one — the partial being the case that matters, since one card is the whole difference — that it opens NO socket, and that its sentence carries the width, the percentage and `Manage box`. It asserts the unanimous run passes through and narrows to its one set, and that both operator overrides still work on a run with no hint at all. D76's widening rule is still asserted with the flag lifted at the module, the way `MAX_BYTES` is lowered rather than a 32 MB body being put through a harness that runs at every turn end.

**`app/tests/capture-claims.spec.ts` asserts the note in both directions too**, on one stub differing in one boolean, because an outcome assertion cannot tell "drawn correctly" from "drawn always".

**Eleven mutation arms, all caught.** The refusal deleted; firing for the operator too; firing for every game; letting the partial box through; the way-forward clause removed; the width figure dropped; the registry flag flipped off; the measurement removed from the entry; the flag authored on a `category` game; and the capture note wired to never draw and to always draw.

---
