# Screens

The screens of the app, one row of `ROUTES` in `app/src/App.tsx` each. The screen's key is its `screenKey`.

## Screens

- `home` — Home — The start page, drawn as a picture of the product.
- `capture` — Capture — Photograph each card of a box as it feeds, with section dividers and an undo stack.
- `review` — Review — Answer the questions the pipeline parked, and open the runs sheet to identify, join and emit.
- `pricing` — Pricing — The one worklist of every unsent copy, with its price, its holds and the files to write.
- `orders` — Orders — The pull stage of the orders hub: fetch orders and see what to pull.
- `shipping` — Shipping — The ship stage of the same hub: lanes of envelopes and parcels, joined to orders.
- `revenue` — Sales — The gross-revenue retrospective. It leaves out canceled orders and never claims profit.
- `inventory` — Inventory — The one owner view of stored cards: find a card, see where it is, move or retire it.
- `codes` — Codes — The dormant code-card screen: read a box's QR codes into the ledger and hand a lane's codes to a buyer.
- `slabs` — Slabs — The ledger of graded slabs, with each slab's value.
- `fulfillment` — Cards to Pull — The Fulfiller's whole product: cards to pull in box-walk order, with photo confirm and mark sold.
- `gallery` — Kit — Every primitive the app is built from, on one page.
- `product` — Product History — One product's market history, with the owner's own sales marked.
- `runs` — Runs — Opens Review's runs sheet. The route stays so an old link still works.
