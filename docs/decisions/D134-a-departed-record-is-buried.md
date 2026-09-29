## D134 — A departed record is buried

**Settled 2026-09-11, on the owner's word.** Told that a whole-box merge (D83) carries only
the on-hand cards, leaving sold and retired records behind in a box that ruling 3 would then
refuse to delete forever, the owner's answer was direct: *"I just need a history log
frankly"*, and asked for a screen to read it — *"having a graveyard accessible just for
potential data giggles is worthwhile having"* — and confirmed the photographs should go with
it: *"yes it should auto delete the photos."*

This amends D10's owner ruling 3 (2026-08-23): "a box may not go while ANY card in it is
sold, retired, or listing-held — those records are history and commitments, not clutter."
The sentence was right and the remedy it named was too small. A departed record's history is
not lost by letting its box go; it is lost only if nothing keeps the record when the box
does. So ruling 3 keeps its shape and gets a second door: a sold, retired or moved record no
longer blocks the delete — it is **buried** first.

### What is built

1. **`DELETE /boxes/<box>` no longer refuses on a departed record.** `do_delete_box`
   (`server/capture_server.py`) still refuses `box_not_empty_of_commitments` for an on-hand
   card an active listing holds — D34's ground, untouched — but a card in
   `master.TERMINAL_STATES` (sold, retired, moved) is no longer a blocker at all.

2. **A departed record is buried before its files go.** One `buried` event per record,
   carrying it whole. A new route-written event, `BURIED = "buried"`, added beside
   `BOX_DELETED` in `SERVER_EVENTS`. Written through the same `_history` call every other
   route-level event uses, inside the same `Store.write()` as the record's own deletion, so
   the line and the deletion commit together or neither does. The line carries: `box`,
   `index`, the box's own name as it stood, `state`, `state_at`, `captured_at`,
   `capture_id`, `run`, `game`, `name`, `number`, `printed_total`, `set_hint`, `sku`,
   `condition`, `rarity_claim`, `product`, `note`, `retire_reason`, `moved_to`,
   `photo_sha256`, `photo_reclaimed_at`, and `order` — the order this copy was pulled
   against, if `Ledger.holder_of(capture_id)` finds one.
   **The digest is computed from the photograph's bytes in the moment before they go**, the
   same way D89's reclaim already does it, if the record does not already carry one; a
   moved tombstone's file already relocated with the transplant at move time, so its digest
   stays whatever the tombstone already had — usually none.

3. **The photographs go, on the owner's word.** Every departed record's photo and sidecar
   are unlinked in the same loop that unlinks an on-hand junk card's — D10's "files inside
   the block, photo before sidecar" rule, unchanged. This is a real loss and it is
   deliberate: debt-style, named here rather than discovered later. What is kept
   is the digest, not the bytes — the same trade D89 already made for a sold card's
   photograph, now made for every door a card can leave a deleted box through.

4. **`GET /graveyard`, the merge of two sources into one shape.** A departed card is either
   still standing in a box nobody has deleted (a `sold`/`retired`/`moved` record, read by
   the indexed `state` column, three `where()` calls) or it survives only as a `buried`
   line (`store/db.py:events_named`, `store/session.py:Store.buried()` — `history()`'s
   narrower sibling, an unindexed scan over the `event = 'buried'` rows rather than the
   whole log). `do_graveyard` merges both into `_departed_row`'s one shape, newest departure
   first. The two sources never overlap by construction: a record moves from the first to
   the second exactly once, at the moment its box is deleted, and there is no route back.

5. **`#/graveyard`, the twelfth route.** `app/src/Graveyard.tsx` + `.css`, modelled on
   `Codes.tsx`'s fetch-a-list shape: a Segmented filter (All/Sold/Retired/Moved/Buried), a
   text search over name, number, SKU and box name, and a `.bn-table` that becomes a
   stacked card at 639px. Read-only — no photograph (buried cards have none, and the
   screen stays out of `scripts/views.txt`'s exposure rows), no price, no control that
   writes. `library` group, hotkey `g`.

6. **The Manage box sheet's delete panel draws the new boundary.** `BoxOps.tsx:DeleteBox`'s
   pre-emptive `Notice` no longer says a sold or retired card refuses the box; it says how
   many departed records will be buried and that their photographs will be deleted, and
   names only a listing hold as a real refusal. The success toast's receipt gains a buried
   count. `BoxDeleteResult.buried` is the wire field both read.

### What is lost, stated rather than discovered later

**Sale and retirement undo on a deleted box.** Reversing a sale or a retirement is a route
over the still-existing record; once a record is buried there is no record to reverse, only
a line describing what happened. This was already true the moment a card's box was deleted
in the old world too — the box simply could never be deleted while such a record stood. The
practical change is that the box no longer has to stand forever for the undo option to keep
existing; the undo option and the box now go together.

**The departed rows and copies-list entries for that box on `#/inventory`.** A buried record
is not a row anywhere a box is rendered — only `#/graveyard` reads it. Searching by name
still finds it there.

**D36's realign by digest, for a run still un-joined over a deleted box.** A moved card's
digest and its photograph both travel with the transplant, so realign still works for those.
A sold or retired card's digest is kept in the burial line, but the photograph it would be
checked against is gone — the same boundary D89's reclaim already draws for a sold card
whose photograph was reclaimed while its box still stood.

**`next_index` for a deleted box number restarts at 1.** Already true before this decision —
"a deleted box is a box the store has never heard of" (D10) — and unchanged: this decision
only widens which boxes may reach that state. D10's permanent-gap promise holds inside every
box that still exists.

### What is recorded rather than mitigated

**Old per-position `sold`/`retired` history lines are not rewritten or removed.**
`_state_before_sale` and `_state_before_retirement` scan backwards from the most
recent line for a given position key; a box number reused after a delete writes its own
newer lines for the same keys, which those readers find first. A stale line from a deleted
box therefore sits inert beneath a live one rather than being cleaned up — the same shape
D36's `refuse_reallocated` already treats as a hazard worth refusing a run over, not worth
silently repairing.

### Amendment, 2026-09-26: Move Moved out of Graveyard

**The owner's report on the preview review, verbatim:** *"in graveyard, when i clikc moved
or buried i see the same list."* Measured on a copy of the owner's real store: 1,358
departed rows. 264 were `moved`, every one of them out of box 5, later deleted. So all 264
were also `buried`. Not one `moved` row was ever also sold or retired.
**"Buried" is not a way a card left. It means that its old box is gone. A moved card is alive in another box.**

**The owner's ruling, verbatim choice:** *"Move Moved out of Graveyard."*

This narrows what point 4 above calls a departure. `MOVED` still joins
`master.TERMINAL_STATES` (D83, unchanged). A box may still be deleted with a moved
tombstone in it, and that tombstone is still buried the same way point 2 describes. But it
is no longer one of the states `GET /graveyard` answers with. A moved record was never a
card that left the store. It is a tombstone at its old key. The card itself is alive at
`moved_to`, exactly as sellable as before. Burial still happens to the tombstone when its
box goes. Nothing about writing the `buried` line changes. The amendment is which
departures `do_graveyard` (`server/capture_server.py`) reads back, not which lines the
store writes.

**What changed:**

1. **`GET /graveyard` filters `moved` out of both its sources.** The in-box half reads
   `master.TERMINAL_STATES` minus `MOVED`. The buried half skips any `buried` event whose
   `state` is `moved`. A moved record, standing or buried, no longer reaches this route.
2. **`#/graveyard`'s filter row drops from five tabs to three: All, Sold, Retired.** No
   Moved tab and no Buried tab. `buried` is a fact about the box, not a third way a card
   left. It now draws as a small quiet tag on the Where cell. The words are plain: "Its box
   was deleted." The screen never types the pipeline noun "buried" itself (D196).
3. **A moved card is found from the card ITSELF, on `#/inventory`.** `Card.moved_from`
   (`store/master.py`) was already on the wire, unread by any screen. `CardHero.tsx`'s
   `CardDetailsSection` (shared by `BoxBrowse.tsx`'s card pane) grows one Provenance fact,
   "Moved from". It names the old box by name (D259), or "another box" when that box is
   gone. That is the same honest fallback `Graveyard.tsx`'s own `movedToName` already used
   for `moved_to`.
4. **`docs/specs/` and this entry are the record of the narrowing.**

**What is unchanged:** a moved tombstone is still buried. It still keeps its digest and
still loses its photograph — points 2 and 3 above are untouched. The only door this entry no
longer counts as "a departure the graveyard shows" is the one that was never a departure
at all.

---


