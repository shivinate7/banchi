## D252 — A wrong answer gets a correct route, and the SKU it leaves is over-listed by exactly what it gave up

**AMENDED (`D-identity-follows-the-sku`).** The route upserts the chosen row. It writes one
binding through `bind_sku`, instead of seven fields by hand. Its undo derives the identity
again, rather than restoring seven stored values. `sku_unchanged` stays, with a new remedy
text. A new sibling press, confirm, answers the case this entry cannot: the SKU is right, and
the drawn name is wrong. The outcome this entry protects stays protected. The D34 release of
the old SKU is untouched. The next live reconcile still shows what to lower.

**The owner found three cards on the live server, 2026-09-23.** Nothing was written yet. `4/176` read "Daisy!" and was answered onto SKU 9189722 (Lilting Lullaby). The right row was 9197749 (Daisy!, 196/219, Near Mint Foil). `4/442` read "Pyke, Returned" and was answered onto 9199579 (Vex, Apathetic). The right row was 9191942 (Pyke, Returned, Alternate Art). `6/563` read "Frigid Jewel" and was answered onto 9197044 (Rengar, Unseen). The right row was 9189327 (Frigid Jewel). All three wrong SKUs had already gone out. `POST /review/<box>/<index>/answer` with `{"undo": true}` refused every one as `undo_too_late` (D28). The message said: "that SKU is already out of this Mac ... correct the card by hand." There was no hand to do it with.

**The owner's ruling, verbatim:**

```
Build a correct route: a "this answer was wrong" press on Review and inventory. It
rewrites the card's SKU to a catalog row, records the old SKU as over-listed by
one, and the next live reconcile shows exactly what to lower on TCGplayer.
```

**A new route, `POST /inventory/<box>/<index>/correct`.** It is not a branch on `do_review_answer`. D4's whole first half asks which queue entry governs the answer. `_answer_target` refuses `not_in_queue` outright. A card this route was built for holds no queue entry any more. `do_review_answer` already cleared it, correctly, for the wrong row. So the new SKU is re-read the same way a D46 `from_catalog` answer's row is. It comes out of `_catalog_for_card`'s export, inside the write lock. The wire is never trusted. `sku_not_in_catalog` is the same refusal, reused verbatim.

**The old SKU is released through `Listing.release` (D34).** This is not a second mechanism. `pushed`, `staged` and `live` are counts on a SKU, never addresses. D7 amended says so in as many words. No field anywhere records which card backed which listing. What D34's own release already states for a box giving up its copies is true here too. One fewer physical card now backs whatever the SKU's counts claim. So one copy of the least-committed stage is given up — `pushed` first, then `staged`, then `live`. A correction is the same event, run on one card instead of a whole box.

**Item 2 of the brief was measured before anything was built.** `pipeline/livecheck.py:compare` is what `pkmnscan reconcile --live` runs. Its own bucketing weighs `pushed+staged` against `live+sold`, per SKU. It has no notion of which physical card backs a listing. Correcting a card's identity moves neither number by itself. Only a release does. Once `Listing.release` runs, the corrected-away SKU's claim no longer covers what a fresh live export still shows. `compare` then reads it into D109's own `beyond` bucket: "TCGplayer's own quantity for a SKU this pipeline never sent." That bucket was not changed. `harness/tests/t7_store_and_seams.py:check_correct_answer` proves this against the real module. A live export naming the old SKU's still-live copy lands in `report.beyond` after the correction. It lands in neither `agreed` nor `unexplained`. No second mechanism was built.

**The new SKU gets no listing write.** Choosing a catalog row is not pushing one. That stays `emit`'s job (D54). Nothing here touches the new SKU's `pushed`, `staged` or `live`. Only `emit` and `reconcile` move those.

**The stored name follows the catalog.** This is the owner's ruling. A card wrong about its SKU is wrong about its name too. `card.name` is what `#/inventory` and `#/orders` draw as the card's identity. It stops saying the wrong product's name the moment the SKU does. `set_name` and `rarity` are set from the same row a D46 `from_catalog` answer already sets them from.

**It goes both ways, D28's shape.** `{"undo": true}` on the same route reads back the pair the correction overwrote. `_history`'s `restores_to` extra reuses `_answer_before`'s own shape. The released copy is handed back through the SKU's own public writers. `bump` restores `pushed`/`staged`. `set` restores `live`, since `bump` refuses `live` by name (D115). The ground truth for "is there something to reverse" is the card itself. Its `sku` and `condition` must still match what the newest `sku_corrected` line wrote. A corrected card holds no queue entry, so there is no `cleared_by_human` flag to read the way `stood_down` reads one. `undo_too_late` is checked on the card's CURRENT sku. That is the same guard `do_review_answer`'s own reversal checks. An undo that would leave a listing an import file already claims is refused there too.

**The history event carries its own name.** It is `sku_corrected` and `sku_correction_undone`, never `answered`/`unanswered`. `corrected` was already spoken for — D3's capture-claim edit, the set hint and the finish toggle. Reusing `answered` would make a corrected card look like an ordinary D4 answer in the one place meant to say which happened.

**The screen shows only on `#/inventory`.** This is the owner's ruling, verbatim in intent: "Inventory only." `app/src/CardHero.tsx` carries `ListingCorrection`, inside `CardDetailsSection`'s new `correctable` prop. It DEFAULTS FALSE. That is an allow-list of one screen. The owner's own wording says so, amended after the first round. A default of true would hand the control to a third screen. That would happen the day it mounts this pane, with nothing to opt it in first. `BoxBrowse.tsx` passes `correctable` at its one call site. That is the smallest edit this ruling reaches into a fenced file for. `OrdersWalkPane.tsx` needs no flag at all now. Omitting one already means that no control shows. `#/orders` draws nothing for it. No reserved gap is left behind either.

**The control shows only for an identified, on-hand card.** Those are the same two conditions the route itself refuses on (`not_identified`, `card_departed`). So the control never offers a press the server would only reject. It reuses D46's own picker — `CatalogPanel` and `CandidateButton`, exported from `ReviewQueue.tsx` for this reason. That file's own header states the rule: "added to inventory and both screens get it, not a fork." A receipt with Undo follows the write, `Inventory.tsx`'s own toast shape. No user-visible string names a decision id, a repository path, or a pipeline noun (D196). The control reads "Wrong card?" and "Correct the listing." It never reads `emit` or `sku_corrected`.

**The slot keeps its own height when the card leaves eligibility (D118).** A sale elsewhere on this card — `Mark sold`, a different control — turns `card.state` to `sold`. This control's own content then turns to nothing. `CardLocations.css`'s `.card-locations-action` rule is reused, not invented. The wrapper always renders. `min-height` reserves `Wrong card?`'s own height, whether or not anything stands inside it. `app/tests/inventory.spec.ts`'s own whole-page sweep proved the gap first: a vanished control shrank the Details panel by 44px. Nine elements below it moved.

**The undo restores the stamps, not only the counts.** `Listing.release` restamps `staged_at` and `live_as_of` on its way out. That is D34's own rule — an observation made now. The `sku_corrected` line now carries both stamps at their PRE-CORRECTION value. `_give_back_listing` puts both back verbatim, once the counts themselves are restored. Without this, a correct-then-undo round trip reads as a fresh reading nobody took. That is exactly what `staged_stale` and `reprice` exist to catch. `check_correct_answer_live_release` proves this, and the `live` stage of the release itself, mutation-tested on both.

**What this does not attempt.** A departed card (sold, retired, moved) refuses `card_departed`. Correcting a SOLD card's SKU is a larger question. It would also touch `sold_here` and a buyer's own order. This route does not answer that question. Nothing here uploads to TCGplayer. The release is a record in this store alone. The next `pkmnscan reconcile --live` tells the operator what to go and lower by hand.

**Governed by:** D4 (the review queue's one-tap answer, and the guard against a free-text SKU this route does not weaken), D28 (the twenty-second undo shape, and the `undo_too_late` boundary this route reaches past), D46 (the catalog lookup and its re-read-on-the-server rule, reused rather than re-argued), D87 (the store-wide live reconcile this route's release is read by), D109 (the `beyond` bucket that is the whole of item 2's proof), D118 (the reserved slot, `CardLocations.css`'s rule reused), D196 (no decision id, path or pipeline noun on screen), D220 (the order walk is inventory's own pane, in a mode — why `#/orders` gets a prop and not a fork).

---

### Amendment — the rarity was never carried, and the number was never touched

**The owner found three more cards on the live server, all corrected through this route.**
`4/176`, `4/442`, `6/563`, found 2026-09-23. Each read `rarity = NULL` afterward. Each kept
the model's misread `number` — the field this route exists to fix.

**Rarity was a missing key, not a missing line.** `do_correct_answer` already read
`chosen.get("rarity")` and wrote it onto the card. The row it reads, `_catalog_row`, carried no
`"rarity"` key at all. `_candidate_rows` — the review queue's own row shape — has carried `rarity`
since D213. `_catalog_row`'s own docstring claims "identical keys", and did not have them.
`chosen.get("rarity")` therefore always answered `None`. This hit two readers: this route, and
`do_review_answer`'s own D46 `from_catalog` branch. Fixed once, at `_catalog_row`, so both agree
with `_candidate_rows` rather than carrying two copies of D213's rule.

**The number was never set. This entry's first draft left that gap open.** Item 2 above answers
what a correction does to a SKU's LISTING counts. Nothing there touched a card's own `number`
field. The orchestrator's ruling, within D36: a correction is a human choosing a catalog row off
the photograph. That is the same act that already rewrites `set_name`/`rarity`/`name` above. A
chosen row's number is just as much "what this card is" as its name. So `card.number` and
`card.printed_total` are now set from the same row, inside the same transaction.

**Checked against D36 and D183 first, as the brief required. Neither governs this field.** D36
decides which SLOT a photograph is in, keyed on `photo_sha256`. It says nothing about the identity
fields a slot's occupant carries. This route never touches a position key. It never re-binds a
slot. It writes nothing `realign` reads. D183 decides where a photograph's BYTES are filed. It is
equally silent about `number`. A card's `cid` and its stored name are untouched here. The model's
own reading is not lost. `identifications.json` still carries it verbatim. The `sku_corrected`
line's `restores_to` now carries the old `number`/`printed_total` pair too. The misread stays
recoverable two ways: from the run record D36 protects, and from this route's own undo (D28).

**A REVIEW ROUND CAUGHT A SECOND DEFECT IN THE FIRST FIX, BEFORE MERGE.** Worth its own
account. It is exactly the mistake this whole entry warns about. The first draft here split
every game's `Number` cell the same way. All three real cards are Riftbound. Riftbound is
not `number_and_printed_total`. It is `printed_code` (`pipeline/games.py`).
`pipeline/join.py:_key_printed_code` reads `card.number` WHOLE and verbatim. It never
consults `printed_total` at all. Splitting `"056/298"` into `("056", "298")` would have
broken a later store-backed join (D188). It would also have wrongly filled `number_key`.
`pipeline/pricearchive.py`'s own comment documents that field as empty by design for a
game with no denominator. Riftbound also prints 13 double-sided token cells, `"T01 //
T02"`. A `/`-splitting rule finds two candidate splits in that string. Both are wrong.

**The fix is GAME-AWARE, through the game's own key strategy, never a hand-typed game list.**
`pipeline/join.py:catalog_number_fields(game, raw_number)` reads
`games.get(game)["join_key"]`. A `number_and_printed_total` game (Pokemon) still splits.
It does so through `store/numbers.py:split_catalog_number` — the fourth member of that
leaf module's family. `join_key` composes. `display_number` draws. `strip_set_code`
repairs. This one decomposes, on the LAST `/`, because a secret rare's numerator can carry
no slash of its own (`"302*"`). Every OTHER strategy — `printed_code`, `name_only`,
`not_joined` — stores the cell VERBATIM. It leaves `printed_total` empty, exactly as every
other writer for that game already does. `_catalog_answer` now returns the game it
resolved alongside the row. That is the same game `_catalog_for_card` read the export as.
`do_correct_answer` never re-derives it and never re-parses the export a second time.

**`number_key`/`number_display` are still never set directly, here or anywhere else.**
`store/master.py:_card_columns` derives both from `card.number`/`card.printed_total`. It
runs on the very next write any card makes. `do_correct_answer` sets the two fields and
nothing more. That is the same chokepoint every other card write already passes through.
A `printed_code` correction leaves `number_key` empty, on purpose. `number_display` still
reads right, because `join.display_number` falls back to the whole cell when
`printed_total` is absent.

**The undo carries both, but a MISSING key is not a `null` claim.** `restores_to` gained
`number`/`printed_total` beside `sku`/`condition`/`set_name`/`rarity`/`name`. The three
real lines on the owner's store predate this fix. They carry neither key at all. That
route never touched those fields until now. Reading a missing key as `None` would ERASE a
real number the old line was never responsible for losing. That is the exact loss this
route was built to stop. `_reverse_correction` now checks presence before it restores. A
line that records the pair puts it back verbatim, including `None`, the same as `sku` and
`rarity` already do. A line that does not leaves the field exactly where it stands.

**Rarity reaches `do_review_answer`'s own `from_catalog` branch too, proved separately.**
`_catalog_row` is the one place both routes read a chosen row from. The fix at that
function fixed both readers at once. T7 now asserts `card.rarity` after such an answer and
after its own undo, not only after a correction.

**T7's `check_correct_answer` now asserts the game-aware shape both ways.** It checks the
real Riftbound fixture row `8925897` (`Adaptatron`, `056/298`, `Uncommon`, stored WHOLE)
and a Pokemon row from the committed SV09 export, split correctly. Each is checked against
the persisted `number_key`/`number_display` columns. Each is re-joined through the real
`_key_printed_code`/`_key_number_and_printed_total` function, to prove the stored number
would still find its own row. A third T7 check, `check_catalog_number_fields_round_trip`,
round-trips every distinct `Number` cell across all four committed exports through
`catalog_number_fields`. It includes the double-sided token cells, and reports the count.

**The repair script's own docstring named the wrong blocker for undo-then-redo, fixed too.**
`sku_unchanged` never applied. After an undo the card's SKU is the OLD one
again, so re-correcting to the NEW one is a real change. The real blocker is
`undo_too_late`. The UNDO step itself refuses the moment the card's current, already
corrected, SKU carries a pushed, staged or live copy. Measured on the owner's store,
2026-09-23: `4/442`'s corrected SKU 9191942 reads `pushed=3, live=3`. Undo-then-redo
cannot even begin there. The script stays the one mechanism for all three cards, using the
same game-aware rule as the route.

