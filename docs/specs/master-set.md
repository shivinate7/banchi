# Master set: see which cards to pull before they sell

**Status: DRAFT. Nothing here is built.** It extends the Sets view on `#/inventory`
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

## 2. The master list is the `pulled` retirements

There is no new store fact. **A card is in the master set when the store holds a copy of its
SKU retired with reason `pulled`** (D26, retired is a terminal card state;
`store/master.RETIRE_REASONS`). Pulling stays the existing retire press, with its receipt and
its undo. Undoing the retirement takes the card back off the master list.

- The key is the SKU, so a foil and a normal printing are two master-list entries. The Sets
  view already keys rows on the SKU (`do_pipeline_sets`) and draws `printing` on each row.
- A card with no SKU (`sku_unknown`, D258, identity follows the SKU) cannot be on the list. It
  shows as not collected, with no badge change.
- `pulled` already has other meanings for the owner: 10 Riftbound cards on the owner's store are
  retired `pulled` today. They count as collected from day one. Open question 7.1 asks whether
  that is right.

## 3. What the route adds

`GET /pipeline/sets` (`server/pipeline_routes.do_pipeline_sets`) gains one boolean per row,
`collected`. It is true when any card with that SKU has state `retired` and `retire_reason`
`pulled`. It is one more `cards.select` over retired cards, inside the same plain read: no
socket, no write, no lock.

A set that holds only pulled copies and no on-hand copy has no row today, because the route reads
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
  reason `pulled`. This draft adds no write to the Sets view.

## 5. A pulled copy that is already live on TCGplayer

The owner corrects it after the pull with a negative `Add to Quantity` (D100, never delete to
lower a price). What exists today, measured in code:

- `banchi reconcile --phantoms <my-pricing.csv>` lists SKUs live beyond what is on hand. A
  pulled copy is no longer on hand, so it shows there. It is read-only.
- `emit --live-guard FILE` trims rows so TCGplayer never holds more copies than are here.
- `cli/cmd_emit._Take` writes negative take-off rows only for withheld SKUs, not for a retired
  copy.

So the correction path for one pulled copy is the phantoms worklist today. Open question 7.2 asks
whether it should be one press.

## 6. Later: cards the store has never held

The full checklist adds rows for cards printed in the set that the store has never held, with
`qty: 0`, not collected. Pokemon can read them offline from `vendor/pokemon-tcg-data/catalog.sqlite`
(`pipeline/catalog.CatalogIndex`, D15, the catalog is vendored). Riftbound has no vendored
catalog. It would need the TCGplayer catalog the stock photos already read
(`pipeline/stockimages.StockImages`, D301, stock photos are hotlinked). This is a second step,
because it is the only part that needs a catalog and the network.

## 7. Open questions for the owner

1. Do the 10 Riftbound cards already retired `pulled` count as collected, or does the master set
   need its own reason (a fifth `RETIRE_REASONS` member, such as `master_set`)?
2. Should the Sets view offer a one-press "take the live copy off" after a pull of a live card, or
   is the phantoms worklist enough?
3. Should "Last copy" also count captured copies not yet identified? Today the route reads
   `identified` cards only, so a fresh capture of the same card does not count yet.

## 8. How it is checked

- Harness test T7 grows a case: one SKU with one on-hand copy and one `pulled` copy reads
  `collected: true`. A SKU whose only copy is `pulled` reads `qty: 0`.
- An app spec at 1440 and 820, light and dark: the filter hides collected rows, and the Last copy
  mark shows on a `qty: 1` row only.

## 9. Freshness, as it stands

The Sets view re-reads on open and after a write made on the Inventory screen. It does not poll
and does not re-read on tab focus. A sale on `#/orders` or the Fulfiller's screen shows up only
when the view opens again. So "Last copy" can lag a sale made elsewhere until then. That lag
loses no card: the worst case is a tile that says Last copy for a card already sold.
