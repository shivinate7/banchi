## D134 — A departed record is buried, not kept; the box goes; and the graveyard is where the departed are read

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
   deliberate: `docs/DEBTS.md`-style, named here rather than discovered later. What is kept
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

---


