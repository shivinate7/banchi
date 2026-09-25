# Box map deliberation: sizing and the options weighed

**Status: reasoning, not a spec.** `docs/specs/box-map.md` is the spec of record for the box
map. It carries the owner's own words, the v1 scope table, the primitives, the ordering key,
the screen, and the open questions. This file holds only what that spec does not: the sizing
estimate, and the options each owner question weighed before the owner picked one.

## Sizing

Three build lanes, each Sonnet-shaped.

| Layer | Files | Work | Size |
|---|---|---|---|
| Safety (slice 0) | `server/capture_server.py:_move_one`, `cli/resolve.py:realign` | Refuse on `Submissions.overlap`. Follow a tombstone's `moved_to` to its transplant, checked by `cid`. | S, about 80 lines plus tests |
| Store | `store/master.py` | Three new methods: `remove_divider`, `move_section`, `unmove`. | M, 200-300 lines with docstrings |
| Server | `server/capture_server.py` | One plan function, a move route with a preview, an undo route, and a `card_moved` answer that names the destination in words. | M, 300-400 lines |
| Front end | New `BoxShelf.tsx`/`.css`, plus `Inventory.tsx`, `server.ts`, `types.ts`, `keys.ts`, `demoServer.ts`, and `Fulfillment.tsx`'s walk sentence | The map, pointer drag, tap pick-and-place, a keyboard grid, the receipt, undo | L, 900-1,200 lines |
| Tests | `harness/tests/t7_store_and_seams.py`, new `+app/tests/boxshelf.spec.ts` | T7 cases below, plus drag, keyboard, tap at 390, a sealed target, the receipt text, both themes, and the D50/D117/D118/D195 floors | M-L, about 700 lines |

T7 cases: the section lands at the back, contiguous, in order. The destination gets a divider
with the name. The source loses the divider, and the other names stay. Moving the divider at
index 1 works. A sealed destination is refused. A card with a live claim is refused. A stale
aim is refused. An injected failure writes nothing. Undo restores the exact state. Undo is
refused after a later write. `realign` follows `moved_to`. Queue and cache entries are
re-keyed.

Total: about 2,500 to 3,000 lines with tests and docs.

What can ship first, on its own, before the rest: the safety slice alone protects today's "Move
to box" with no new screen. A read-only map needs only the front end, since every figure it
draws already sits on `GET /boxes`. A section move without drag is the feature, complete, for
every input. Drag, pick-and-place, the keyboard grid and undo are the feel the owner asked for,
built on a write already proven.

## The owner's questions, and the options each one weighed

Every answer below is now a ruling, recorded in `RULINGS.md`'s "Box map" section. This keeps
only the alternatives the owner did not pick, and why the recommendation read the way it did.

- **Where do dropped cards land in the section?** The back always (chosen), a chosen point
  between two sections (needs a new per-card order key, its own decision-sized piece of work),
  or the back for v1 with the ordered drop recorded as the next step. The owner's own picture
  named "before or after any section", so v1 carries the ordered drop, not the simpler back-only
  form (`docs/specs/box-map.md` §4).
- **Does the divider travel with the section?** Yes, with its name (chosen), or no, so the cards
  join the destination's last section, or ask on every drop.
- **When does a drop write?** The chosen answer is at once, with the receipt as the
  instruction and Undo on U, per `docs/DESIGN.md`'s no-dialog-on-a-reversible-act rule. The
  other options: a preview with one Move press, or several drops queued behind one
  "Apply N moves" press.
- **What does Undo do?** The chosen answer is an exact restore while neither box has
  changed since, and a new move after that. The other option was no special undo at all, so
  moving back lands at the back like any other move.
- **Does a moved card keep its join to its run?** D165 refused to follow a card into a drawer
  nobody asked about, written when a run was the whole unit of work (D48). D180 replaced D48, so
  the join can now follow a card by its own name (`cid`) rather than by a guess. Measured: 99 of
  the owner's cards had already lost their pricing surface to a move, under the old rule. The
  owner's ruling follows the card (`D-a-moved-card-keeps-its-price`).
- **Where does the map live?** The chosen answer is a Shelf view inside Inventory, which
  keeps D31's one screen for stored cards. The other options were its own screen and nav row,
  or a sheet opened from the box rail.
- **What is in v1?** Sections, whole-box merge, box split, and a section to the back of its own
  box (chosen). Single cards and ranges stay in the walk's own tick-and-move for now.
- **Does the map show money?** Counts only (chosen, since no per-box value sits on the wire
  today), or a market-value sum per box and per section, computed fresh from the price archive.

## Found in passing

Two more findings sit in `docs/specs/box-map.md` §9 already: the false comment on `Box` in
`store/master.py`, and the doubled separator on the Manage box sheet's eyebrow. One more stays
open there too: whether D134 (a departed record is buried, not kept) makes D83's "a merged-out
box cannot be reclaimed" stale. That reading is proposed, and still awaits the owner's word.
