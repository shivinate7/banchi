## D170 — A Pokemon run names its sets

**A game whose category cannot be fetched whole may not have its fetch chosen by cards that said nothing.** The owner ruled this.

Three options went to the owner for the Pokemon catalogue fetch. The fetch sat at 97.24% of `tcg_export.MAX_BYTES`. The options: refuse early under the cap, leave it visible, or fix the cause. The owner chose the third: make unhinted Pokemon cards impossible.

### The measurement, and what it is not

**One forced whole-category Pokemon fetch: 32,629,598 B over 222,849 rows.** That is 97.24% of the 33,554,432 B ceiling the download is refused past. Headroom is 903 KB. The one set the owner's Pokemon cards all name is 238,482 B. The widening is 137x, and it lands two per cent short of a refusal.

**D76 wrote that a widening is always safe.** For this category it is 903 KB from a refusal. "Safe" was never wrong in principle. It was unbounded, and one category has now been measured past the point where it holds.

**One unhinted card is enough, and that is D76's rule working correctly.** A set filter is legal only where every card of the game is hinted and every hint resolves. A hint is evidence about the card that carries it. The box stops being unanimous when one card says nothing. The fetch then goes from 238 KB to 32.6 MB.

**This is preventive. Nothing was broken.** On the owner's live store: 543 Pokemon cards, all 543 carrying `ME01`, none unhinted. Riftbound holds 700 unhinted of 1,992. That costs nothing. Its `export_scope` is `category`, so its whole 10,078-row catalogue downloads as one file, however its cards are labelled. The 97.24% figure came from a fetch made to measure the cliff, not from anything this store does.

### Where it is enforced, and why not the other three places

**`server/pipeline_routes.py:_scope_for_run` decides how wide to ask.** It is the one function that does. The press-nothing preview and the paid fetch both call it, so one refusal gets two behaviours. `GET /pipeline/runs/<name>/scope` draws it, since that route already reads a `PipelineRefusal` as data. `POST .../export` refuses with 409 and opens no socket. The operator meets this before the money gate, on the screen D76 built for it.

**Not the shutter. This is the load-bearing rejection.** `app/src/setHint.ts`'s header carries D65's rule. It judges and never refuses. The rig does not stop for an autocomplete at a 623 ms feeder cadence. A capture refused mid-feeder is worse than an unhinted card. It leaves a physical card in the drawer with no record, which renumbers every card behind it. An unhinted card is repairable. A missing record means that the box and the store disagree.

**Not a capture-time precondition.** Refusing to arm without a hint closes the future and does nothing about cards already captured. A client-side gate is not a boundary. The CLI, a stale tab and `requeue` all reach the store.

**Not `#/review`.** Its `ANSWER_FIELDS` are `sku`, `condition`, `undo` and `from_catalog`. Answering a queued question picks a SKU. It cannot write a claim, so a missing hint is not fixed there.

**The cliff belongs to a request, not to a card.** It costs nothing until something asks TCGplayer for a catalogue. That is the general form of all three rejections. The place that sets the width of that request is the only place that knows the game. It also knows the counts, the unresolved hints and the measured bytes, at once. Anything earlier has to guess.

### The rule is a per-game field, because the cliff is not

**`export_needs_hint` in `pipeline/games.py`, with `export_category_bytes` beside it as evidence.** It has the same shape `export_scope` has. It is a claim that must be measured. It is authored only where the measurement exists, and it is false by omission.

**It is not derived from `export_scope`.** Three of the four catalogued entries show why. `sets` is the default, and `pokemon_code` and `one_piece` carry it too. A predicate off `export_scope` would refuse both for a measurement neither has.

**`pokemon_code` shares category 3 and is deliberately exempt.** It sits on the same 32.6 MB cliff. It joins by `name_only`, the blank-`Number` rows, so a set filter buys the match nothing. A code card does not reliably print a set for the operator to read. A hint demanded there is friction with no narrowing at the end. `riftbound` wins its `category` on the same argument. **A hint is refusable only where a hint would have narrowed the fetch.**

**So the cliff stays reachable on the code-card track. That is a named gap.** What covers it is what covered it before. The width is drawn on the preview before the press. `_too_large_sentence` says the scope is why, if the download is ever refused. Closing it needs a narrower transport, a paged or streamed fetch, not a claim the operator cannot make.

**`export_needs_hint` may not be `False` where it would be a lie, and may not be authored where it could never fire.** The `game vocabulary` row of `scripts/docs-audit.py` refuses the boolean on three kinds of entry. It refuses one that names no `export_category_bytes`. It refuses one that names no `tcgplayer_category_id`. It refuses one whose `export_scope` is `category`. That last case is a rule that can never run. Such a game widens by policy and never reaches the cards.

### `chosen_by == "cards"` is the whole predicate, and no run is stranded

**The refusal fires only where the cards under-specified the scope.** These are the four branches that set `chosen_by` to `cards`, and only those four: `no_hints`, `partial_hints`, `unresolved_hints`, `no_hints_resolved`.

**D76's other two voices pass through.** An operator who sends `set_ids` or `scope: category` is `operator`, and is not refused. That is the override, and it is why a refused run is never stranded. The refusal stops the machine widening on a guess. It does not stop a person. A game whose own `export_scope` is `category` is `policy` and never reaches the question.

**The cards are repairable through a path that already existed.** `PUT /inventory/<box>` takes `set_hint` over a whole box or a named selection, in one transactional write. The owner asked for this to fix a hint missed at capture. It is reached from `#/inventory` → Manage box → Set claims. The card-level `PUT /inventory/<box>/<index>` sits beside it. **No second repair path was built.** The refusal names that screen rather than describing a capability.

### The screen says it at the rig, where it is still free

**The capture screen draws a note and refuses nothing.** `GET /games` serves the registry verbatim, so `GameEntry.export_needs_hint` reaches the app. The boolean an operator meets is the same literal the fetch refuses on. No second threshold can drift. The field's head reads `Needed for this game` instead of `Optional`. The meta beside the cursor reads `needed`. The note names the refusal and the screen that fixes it. The resting row says so too, for every card of a sitting nobody pressed `H` on. There, a bare `None` reads as a choice that was made.

**Without that note, the operator's first sight of the rule would be `#/runs`, an hour of captures later.** That is the defect `setHint.ts` exists to end. A refusal without the note would bring it back one register up.

### What proves it

**Both directions, on the same cards, with one flag between them.** T7 asserts that the refusal fires on a bare Pokemon run. It also asserts that the refusal fires on a partial one. The partial case matters most, since one card is the whole difference. The refusal opens no socket. Its sentence carries the width, the percentage and `Manage box`.

T7 asserts that the unanimous run passes and narrows to its one set. It asserts that both operator overrides still work on a run with no hint at all. D76's widening rule is still asserted, with the flag lifted at the module, the way `MAX_BYTES` is lowered. A 32 MB body is not put through a harness that runs at every turn end.

**`app/tests/capture-claims.spec.ts` asserts the note in both directions too,** on one stub that differs in one boolean. An outcome assertion cannot tell "drawn correctly" from "drawn always".

**Eleven mutation arms, all caught.** Each arm was a single defect:

- The refusal deleted.
- Firing for the operator too.
- Firing for every game.
- Letting the partial box through.
- The way-forward clause removed.
- The width figure dropped.
- The registry flag flipped off.
- The measurement removed from the entry.
- The flag authored on a `category` game.
- The capture note wired to never draw.
- The capture note wired to always draw.

---
