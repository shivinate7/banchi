## D-set-view — Inventory gets a second view, grouped by set, and a tap is the ordinary walk

**The owner's request, verbatim, 2026-09-25:**

```
do i have anyway of seeing my inventory by set order? basically a view where i just know
what qty of each card and then can click in if interested and it pops me to inventory
screen?
```

The owner then said: *"send a sonnet builder on it now."*

### The ruling

1. **This is a second VIEW of `#/inventory`, not a fourth screen.** D264's own precedent
   already answered the shape. The box map lives inside Inventory, not beside it. D31 gives
   the owner one screen for stored cards, not several. The set view follows the same rule.
   It is a "Sets" tab beside the existing box walk, both inside the one route.
2. **It answers "what, and how many," never "where."** Every on-hand card groups by game and
   set, in the set's own printed order. One row per distinct card, with its quantity. No
   money: D264's box-map ruling makes the same call, for the same reason. A v1 count view
   shows counts.
3. **A tap is the ordinary walk, never a new one.** `#/inventory?box=<n>&card=<cid>` is
   `BoxBrowse.tsx`'s existing deep link. Review's place pill already uses it. A set row
   points the walk at a card the same way a place pill does. `CopiesPanel` on that screen
   already shows every other on-hand copy of the same SKU. This view adds no walk mechanism
   of its own.
4. **The state it switches on lives in the URL** (D285): `#/inventory?view=sets`. A tap
   clears `view` and writes `box`/`card` in the same `patchViewQuery` call. That is a
   same-path query change, so a history REPLACE, never a push (D201).

### What is built

- `GET /pipeline/sets` (`server/pipeline_routes.py:do_pipeline_sets`). A plain read, the
  same posture as `do_pipeline_value`: no socket, no write, no lock. It reads every card
  whose state is `identified` — on hand, narrower than `do_pipeline_value`'s "not a
  terminal state". A captured-and-not-yet-identified card carries no set or number to group
  by. It aggregates SERVER-SIDE, and never ships one row per physical copy.
- Measured on the owner's own store, a `.backup` copy, read-only: 2,455 on-hand cards, 6
  sets, 771 distinct rows inside those sets, and 4 cards with no set on file. Each of those
  four gets its own row. Nothing about them — no SKU, no name, no number — tells one apart
  from another. Merging them on a shared blank key would have silently collapsed four
  distinct physical cards into one row a tap could reach only one of.
- The grouping key is the SKU, where the card has one. A `sku_unknown` card (D258) groups
  on its own name and displayed number, when it has either. A card with none of the three
  is its own row, keyed on its stable card id (D172).
- The order inside a group is a natural sort over the RAW `number` column
  (`_natural_number_key`): a digit run compares as an integer, everything else as a lowered
  string. This is never a per-game rule. `pipeline/games.py` dispatches a join key by game,
  because MATCHING one spelling against another needs to know which game it is. Ordering
  does not need that. Re-deriving that dispatch here, for a job that only needs monotonic
  order, would be exactly the workaround this repo's "check the primitive first" rule warns
  against. `number_display` (D67) ships for the eye — the same composed form every other
  screen already draws, off the same stored column. The raw column is read only to sort by.
- `app/src/InventorySets.tsx`. Kit primitives only: `Section` for each game/set group,
  `.bn-list`/`.bn-list-row` for the rows, `EmptyState`/`Notice`/`Loading` for the three
  states a fetch can be in. The view switch is `.bn-tabs`/`.bn-tab`, the same pattern
  `Codes.tsx`'s ledger and `Gallery.tsx`'s queue already draw two tabs with. No new kit
  component. No hand-rolled control.
- `app/src/server.ts:getInventorySets`, and `app/src/types.ts:SetsReport`/`SetGroup`/
  `SetGroupCard`.
- `app/tests/inventory-sets.spec.ts`. It covers the grouping, the printed-number order, the
  quantities, and the tap landing on the walk, against a seeded store.

### What this does not do

No write. No search or filter inside the set view itself. The box walk already carries
search, and a card of interest is one tap away from it. No price: the owner's ask was
quantity. D264's ruling on the sibling box-map feature already argued the case for holding
money back from a v1 count view.
