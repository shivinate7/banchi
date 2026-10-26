# Sales: the build plan

**Status: MOSTLY BUILT.** The owner settled this plan in an interview. Each section has its own
status. `docs/specs/sales-findings.md` holds the findings and the constraints. This file holds what
was built from them and what is still owed.

| section | status |
| --- | --- |
| 1. Sold cards, then against now | BUILT (D225) |
| 1. Unsold stock, value over time | BUILT (D236), with sealed stock a counted gap |
| 2. Refunds, layer 1 | BUILT (D225) |
| 2. Refunds, layers 2 and 3 | NOT BUILT. Both need the owner |
| 3. The per-product view | BUILT (D227) |
| 4. The archive | BUILT (D219). The daily price job sweeps it (D224) |
| 5. Ride-along defects | BUILT (D225) |

## The owner's rulings

- **Hindsight against today's prices: build both, as two separate things.** For cards already sold,
  the owner wants to see whether selling then gained or lost against selling now. Separately, the
  owner wants unsold holdings valued over time. A reviewer argued that the first should be refused,
  because a banked profit drawn as a loss trains the reader to hold instead of sell. The owner read
  that argument and ruled against it. The framing in section 1 is the answer to it.
- **The month chart: mark the known faults and leave it alone.** Make no repair and no deletion. A
  future session must ask before it treats the faults as a defect to fix.
- **Refunds: the data exists.** Refunded orders appear in the export. Section 2 explains the three
  ways that holds.

## 1. The two value questions

These are separate features with separate rules. Nothing may merge them into one figure.

### Sold cards: then against now (BUILT)

For a card already sold, compare the price it sold for with the market price today. The owner's own
sales are exact fills, each with a price, a quantity and a date. So this is a measurement, not an
estimate. Rules for how it draws:

- It is a market observation, never a profit or a loss. No label says gain, loss, performance or
  missed. The card was sold, and the money was taken.
- It is blind to what the card cost, and that fact sits beside the figure. A card bought at two
  dollars and sold at eighteen, against a twenty dollar market, is a large gain. This figure draws
  it as a shortfall.
- Direction is a sign and a word, never a color (D278). The palette holds no red and no green.
- Today's price comes from the price archive, with its own age (D225). The screen never fetches on
  its own.
- A name with no reading shows no figure, and never a zero. The count of names with no reading is
  stated on the same screen as any total.

### Unsold stock: value over time (BUILT)

For cards still held, value them at the market and show that value moving (D236).

- The position is the SKU. Every copy is fungible, and no order claims one (D212).
- Quantity comes from the card table's own state, never from the count the marketplace holds. That
  count is a stale mirror until the next reconcile.
- Every mark carries its age. A total carries the count of names it could not mark.
- **Sealed stock has no card record, so it has no quantity in the card table.** Revenue is
  dominated by sealed product, and unsold sealed stock cannot be valued. It is a named, counted gap.

## 2. Refunds

Three layers, in order of what they cost to reach.

- **Already on the wire (BUILT, D225).** `closed_reason` rides on every line's progress. Its value
  `not_shipping` means refunded or cancelled. The screen subtracts it. The screen states the limit:
  the operator records the value when closing a line during fulfilment. It is not the marketplace's
  word, so coverage depends on habit, not on a guarantee.
- **Dropped at the boundary (NOT BUILT).** `refunds` is a field the marketplace sends, and
  `server/order_transport.py` drops it on purpose. Recovering it widens a security boundary. That
  needs the owner's word, named for that field. No session may do it alone.
- **Never modeled (NOT BUILT).** A refund, a return and a partial cancellation have no state in the
  data model. The terminal status vocabulary holds three words, and none is a refund. If the feed
  reported one, it would be stored as is and read as open. First, someone must check what the feed
  reports for a refunded order. Only then can a state be designed for it.

## 3. The per-product view (BUILT)

`#/product` (D227) is one page per product, deep linkable by `?sku=`. It reads `store/pricearchive.py`
first. It falls back to a live read through `pipeline/pricehistory.py` only for a SKU the archive has
never swept. It never writes, and it never starts a sweep. The route is
`server/pipeline_routes.py:do_product_history`. The read is `pipeline/productview.py`. The screen is
`app/src/ProductHistory.tsx`. `scripts/product-history-selftest.py` proves it. It is not wired into
`make check`, following `scripts/pricearchive-selftest.py`.

The page is off-nav. The route's own SKU field is the control a person finds without a query string.
`docs/specs/sales-findings.md` holds the twelve constraints. Three decide the design:

- **The market series and the owner's fills are two kinds of observation.** The series aggregates
  many transactions. The fills are exact. They are never one continuous series.
- **Bucket width depends on when the report is read, not on when the sale happened.** The same sale
  sits in a one-day bucket today and in a seven-day bucket months later. Precision decays for a fixed
  fact, so the width is stated beside any comparison.
- **Nothing reaches back more than 357 days.** The chart states the date its own history begins.
- **Product charts take three price ticks and three date ticks, with faint guides (B7, built).** The ticks sit on the axes of each range chart on `#/product`.

### The posted-price view (OPEN: placement settled, build waits on the gate)

DEBT68. `price_postings` (D243) records every posted price, one row per SKU per press. The owner
ruled to build B first, then A. Both wait for the gate. The gate is closed while one SKU holds a
second posting, meaning `price_postings` rows exceed its distinct SKUs. One posting is a point and
draws no history. Measured on the owner's store: 103 rows over 103 distinct SKUs, so the gate is
closed. Both builds need one new read route over `store/postings.py`, one client function in
`app/src/server.ts` and one wire type in `app/src/types.ts`. Neither writes.

Both builds keep these rules. A posted price is a third kind of observation. It is never joined to
the market line or the fills (D278). A price stays until the next press, so it is a held step. Money
uses `.bn-money` (D221). Use kit pieces and `--bn-*` tokens only. A chart or table holds its size
from first paint (D313: if the person did not move it, nothing moves).

**B, the first build: a Sales section.** A section on `#/revenue`, below the sold products, titled
"What you asked". It has one row per re-priced name: posts, first asked, latest asked, change, and
average sold at. Each name links to `#/product`. It answers which cards were re-priced, and whether
that helped, across the store. It shows the ends of a history, not its shape. It sits on a
gross-revenue screen (D214), so it never claims profit. The period control needs a rule for posts
outside the period.

**A, the second build: an asked-price series on `#/product`.** Each range chart gets a dashed ink step
line. It has one hollow square per posting and one legend entry. Its price axis includes postings. B's
row links are how a person reaches it. It shows the shape of one SKU's asked price against the market
line and the sale diamonds (D212's grain). It adds a fourth mark to four stacked charts.

## 4. The archive (BUILT)

The price-history source has a hard ceiling of 357 days. Anything older is gone. Anything not captured
now ages out on the same schedule. This was the one item where delay cost something nobody could
recover.

The pattern is the readings table and its adopt command. `store/pricearchive.py` is the table.
`pipeline/pricearchive.py` is the walk. `cli/cmd_pricearchive.py` is the press
(`banchi archive sweep [--write]` and `banchi archive show [--sku ID]`).

- **Buckets are keyed by `(sku, range, start)`, never by width.** The ranges overlap. `semiannual` and
  `annual` are both seven days wide, so a width-only key would merge two independent observations.
  D278 forbids that, and D219 argues the key.
- **The archive never deletes a row.** A bucket that a later sweep does not mention stays as it was.
  It may have aged out of the source, or its SKU may have fallen outside a narrower pass. This is the
  opposite of `readings adopt`, which is a full replace.
- **The sweep's subject is every distinct SKU that `cards` has ever recorded.** Sold and held cards
  both keep their rows (D26, D134).
- **The daily price job runs the sweep after its refresh.** The owner's word is "nightly, on the Mac"
  (D224).

## 5. Ride-along defects (BUILT)

Six defects rode along with D225 and are fixed:

- the comparison sentence's lead
- order numbers clipping at 390px
- the product name column's missing height cap
- the fifth period option wrapping alone
- the missing `bn-stagger` on the rows
- the verdict figure with no weight of its own

Two items were questions, not defects, and they stay the owner's. Money in a table is mono, as D221
settles it. The month chart's known faults stay, under the ruling above.
