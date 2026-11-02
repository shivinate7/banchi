# D326 — Banchi's server calls TCGTracking for labels and tracking, in one lane

Banchi's server holds the TCGTracking key and calls TCGTracking itself, both to create envelope labels and to read tracking back.

Kind: build
Plan: docs/specs/order-pipeline.md#the-tcgtracking-pipe-d326 (python)

**The owner ruled it** (waiting-page items 102 to 111). Banchi is the one hub: stock, listing,
orders pulled from TCGplayer, and labels from TCGTracking while orders are fulfilled.

- **The server holds the key** (item 102). No browser extension sits in the middle. The key is
  read on the server only, never sent to the browser, never logged. The shipper number is not
  secret (item 105) and sits beside it in `.env`.
- **Labels and read-back are one lane** (item 103). The order-pipeline spec's T4 (labels) and
  T5 (tracking back) are built together.
- **Two routes spend** (item 106). Labels are the second, each behind its own free preview and
  explicit confirm. D33 (every step is reachable from a screen) says so.
- **Banchi keeps what the imports return** (item 107). If TCGTracking and TCGplayer may hold the
  owner's data, Banchi may too. Every field TCGTracking's answers and TCGplayer's order import return is
  kept, the buyer address and the label file included. This lifts D61's "buyer PII is not
  stored" and D193's address and tracking exclusions. **The public demo still shows no buyer**:
  the demo-mirror scrub (D295, the public demo is the scrubbed real store) drops every new field.
- **The owner keeps marking orders shipped on TCGplayer** (item 108). Who writes tracking back
  is decided after the first live lookup shows whether the tracking number comes back whole.
- **The preview shows the label count and "fee per your TCGTracking account"** (item 109). The
  API exposes no fee, and no free-label count.
- **Insurance is a switch on each order, off by default** (item 110).
- **No canceled-order re-check** (item 111). The owner can void a label, so a label bought for a
  canceled order is not lost. TCGTracking's API documents no void call, so a void happens in its dashboard.
- **One read-only lookup was granted** (item 104). It found `TCG_TRACKING_KEY` and no shipper
  number, so no call was made.

**Reopen** if TCGplayer ships its own envelope tracking, or TCGTracking's API drops `source_order_id`.
