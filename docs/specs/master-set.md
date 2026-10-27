# Master set: see which cards to pull before they sell

**Status: DRAFT. Nothing here is built. Every question in section 7 is ruled.** It extends the Sets view on `#/inventory`
(D293, inventory has a by-set view). It adds no route to `ROUTES` and no nav row (D31, one
owner-side view of stored cards).

## 1. The ask

The owner collects as well as sells. They want to build a master set of each set on the side.
They want a fast way to see, per set, which cards they hold but have not yet put in the master
set, and above all which of those are the last copy in the store. Then they may pull one before
it sells. They do not always pull it.

**No hard stop.** Nothing in this feature may refuse, hold or delay a sale, a send or an order
pick. The last copy stays sellable until the owner pulls it. That rules out a standing "keep one"
rule (it would also reopen D7, duplicates aggregate by SKU: caps live per send, with no standing
key). It rules out the per-SKU `keeping` withhold in `pipeline/decisions.WITHHOLD_REASONS` for
this job too, because that withholds every copy of the SKU.

## 2. The master list is the `master_set` retirements

**Owner's ruling: the master set gets its own retire reason.** `store/master.RETIRE_REASONS`
gains a fifth member, `master_set`, labeled "Master set" on screen. **A card is in the master
set when the store holds a copy of its SKU retired with reason `master_set`** (D26, retired is a
terminal card state). Only that reason counts. The 10 Riftbound cards already retired `pulled`
do not count. Pulling for the master set is the existing retire press with the new reason, with
its receipt and its undo. Undoing the retirement takes the card back off the master list.

- The key is the SKU, so a foil and a normal printing are two master-list entries. The Sets
  view already keys rows on the SKU (`do_pipeline_sets`) and draws `printing` on each row.
- A card with no SKU (`sku_unknown`, D258, identity follows the SKU) cannot be on the list. It
  shows as not collected, with no badge change.
## 3. What the route adds

`GET /pipeline/sets` (`server/pipeline_routes.do_pipeline_sets`) gains one boolean per row,
`collected`. It is true when any card with that SKU has state `retired` and `retire_reason`
`master_set`. It is one more `cards.select` over retired cards, inside the same plain read: no
socket, no write, no lock.

A set that holds only master-set copies and no on-hand copy has no row today, because the route reads
`identified` cards only. **The route also adds those rows, with `qty: 0` and `collected: true`**,
so a set's master list is whole. Their `box` is null, so a tap uses the existing `?q=` fallback
(`InventorySets.openInWalk`).

## 4. The screen

Inside the Sets view, under the set picker:

- **A filter, "Not in my master set".** It lives in the URL, as `?master=open` (D285, filter,
  sort and search live in the URL). Off by default. On, it hides every collected row.
- **Each tile carries one of three marks**, drawn by CSS and named in words, never a typed dot
  (D218, a typed dot is a defect):
  - **In master set**, for a collected row.
  - **Last copy**, for a row with `qty: 1` and not collected. This is the one the owner asked to
    see fast.
  - No mark, for a row with two or more copies and not collected.
- **The set header adds one count**, "38 of 190 in your master set". The denominator is on-hand
  rows plus collected rows until section 6 lands. It is never shown as the set's printed size.
- **Order stays printed order.** The filter narrows the grid. It never re-sorts it.
- **A tap stays the ordinary walk.** Pulling happens there, through the existing retire press with
  reason `master_set`. This draft adds no write to the Sets view.

## 5. A master-set copy that is already live on TCGplayer

**Owner's ruling: one press on the pull receipt.** The owner chose it so they know the take-off
was sent. When a `master_set` retirement leaves the SKU live above what is on hand, the retire
receipt offers "Take it off TCGplayer". The press is the owner's yes for that SKU. This bends
D100 (never delete to lower a price), whose phantom ruling takes a live card off only on the
owner's yes and builds no screen control for it. The bend covers the `master_set` reason only.
D54 (re-emit adds, never subtracts) is not touched: it governs what `emit` writes for copies not
yet sent.

**Owner's ruling: the press at the pull, an owed list behind it.** The retire receipt offers the
press at once. A take-off not pressed, or one that failed, lands on an **owed list on the Pricing
send card** (`SendCard`), with the press beside each entry. It stays there until it is sent and
settled, or the listing already matches, or the retirement is undone. Every try is a send receipt
in the existing outbound log (`inventory/sends/<stamp>/`, `server/send_routes.py`, read by
`GET /pipeline/sends`), so a failure is listed and readable by a session until dismissed.

The press follows D100's phantom take-off exactly:

- **It reads live first**, through `server/tcg_export.fetch_live`, and sizes the row as live
  minus on hand, less copies sold since that read, never above live. At 0 or below it sends
  nothing and says the listing already matches.
- **One row**: `Add to Quantity` minus that excess, price unchanged, through
  `server/tcg_import.push_to_staged` with `listing=True` and a `take_off` mapping of exactly that
  size, then `move_to_live`. TCGplayer clamps a take-off at 0 (measured in D100), so a doubled
  press cannot go below zero.
- **One outstanding per SKU**, as the hold take-off has it: until a live check settles it, the
  press is absent and the receipt says the take-off is on its way.
- **It writes a receipt** naming the card, the copies taken off and whether TCGplayer accepted
  them. A failed push leaves the retirement standing and says nothing went live.
- **Undoing the retirement does not put the listing back.** The copy is on hand again and goes
  out on the next ordinary send. A harness case proves it.

The press reaches TCGplayer, so it needs the seller session the sends already use. With none, the
receipt says so and offers no press.

## 6. Later: cards the store has never held

The full checklist adds rows for cards printed in the set that the store has never held, with
`qty: 0`, not collected. Pokemon can read them offline from `vendor/pokemon-tcg-data/catalog.sqlite`
(`pipeline/catalog.CatalogIndex`, D15, the catalog is vendored). Riftbound has no vendored
catalog. It would need the TCGplayer catalog the stock photos already read
(`pipeline/stockimages.StockImages`, D301, stock photos are hotlinked). This is a second step,
because it is the only part that needs a catalog and the network.

## 7. Rulings

1. **Own reason.** The master set is the `master_set` retire reason only. Old `pulled`
   retirements do not count (section 2).
2. **One press on the pull receipt, an owed list behind it.** A `master_set` pull of a live card offers "Take it off
   TCGplayer". The press is the owner's yes, bending D100 (never delete to lower a price) for
   this reason only (section 5).
3. **Identified only.** "Last copy" counts `identified` cards only, as the route reads today. A
   capture not yet identified does not count.

## 8. How it is checked

- Harness test T7 grows a case: one SKU with one on-hand copy and one `master_set` copy reads
  `collected: true`. A SKU whose only copy is `master_set` reads `qty: 0`, and a `pulled` copy reads `collected: false`.
- An app spec at 1440 and 820, light and dark: the filter hides collected rows, and the Last copy
  mark shows on a `qty: 1` row only.

## 9. Freshness, as it stands

The Sets view re-reads on open and after a write made on the Inventory screen. It does not poll
and does not re-read on tab focus. A sale on `#/orders` or the Fulfiller's screen shows up only
when the view opens again. So "Last copy" can lag a sale made elsewhere until then. That lag
loses no card: the worst case is a tile that says Last copy for a card already sold.
