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