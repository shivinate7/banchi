# D326 — Banchi's server calls TCGTracking for labels and tracking, in one lane

Banchi's server holds the TCGTracking key and calls TCGTracking itself, both to create envelope labels and to read tracking back.

Kind: build
Plan: docs/specs/order-pipeline.md#the-tcgtracking-pipe-the-owners-rulings-d-tcgtracking-pipe (python)

**The owner ruled it** (waiting-page items 102, 103 and 104). Banchi is the one hub: stock,
listing, orders pulled from TCGplayer, and labels from TCGTracking while orders are fulfilled.

- **The server holds the key** (item 102). No browser extension sits in the middle. The key and
  the shipper number are read on the server only, never sent to the browser, never logged.
- **Labels and read-back are one lane** (item 103). The order-pipeline spec's T4 (labels behind
  D33's money gate) and T5 (tracking back) are built together.
- **One read-only lookup was granted** (item 104). It found `TCG_TRACKING_KEY` in the main
  checkout's `.env` and no shipper number. TCGTracking requires both headers, so no call was
  made. The shipper number is the owner's to supply before any live call.

TCGTracking has no endpoint that marks a TCGplayer order shipped. So T5's premise, that
tcgtracking owns mark-shipped, is unverified. The pipe's plan settles who marks shipped, with the owner.

**Reopen** if TCGplayer ships its own envelope tracking, or TCGTracking's API drops `source_order_id`.
