# Sales: the build plan

**Status: MOSTLY BUILT.** The owner settled this plan by interview. Each section carries its own
status. `docs/specs/sales-findings.md` holds the findings and the constraints. This file holds what
was built about them and what is still owed.

| section | status |
| --- | --- |
| 1. Sold cards, then against now | BUILT (D225) |
| 1. Unsold stock, value over time | BUILT (D236), with sealed stock a counted gap |
| 2. Refunds, layer 1 | BUILT (D225) |
| 2. Refunds, layers 2 and 3 | NOT BUILT. Both need the owner |
| 3. The per-product view | BUILT (D227) |
| 4. The archive | BUILT (D219). The schedule is deferred |
| 5. Ride-along defects | BUILT (D225) |

## The owner's rulings

- **Hindsight against today's prices: build both, as two separate things.** On cards already sold,
  the owner wants to see what selling then instead of now gained or lost. Separately, the owner
  wants unsold holdings valued over time. A reviewer argued the first should be refused, because a
  banked profit drawn as a loss trains the reader to hold instead of sell. The owner read that and
  ruled against it. The honest framing in section 1 is the answer to it.
- **The month chart: mark the known faults and leave it alone.** No repair and no deletion. A future
  session may not treat the faults as a defect to fix without asking.
- **Refunds: the data exists.** The owner said refunded orders appear in the export. That is right
  in three ways, which section 2 sets out.

## 1. The two value questions

These are separate features with separate rules. Nothing may merge them into one figure.

### Sold cards: then against now (BUILT)

For a card already sold, compare the price it went for with what the market says today. The owner's
own sales are exact fills, each with a price, a quantity and a date, so this is a measurement and
not an estimate. Rules for how it draws:

- It is a market observation and never a profit or a loss. No label says gain, loss, performance
  or missed. The card was sold and the money was taken.
- It is blind to what the card cost, and that fact sits beside the figure. A card bought at two
  dollars and sold at eighteen against a twenty dollar market is a large gain. This figure draws
  it as a shortfall.
- Direction is a sign and a word, never a color (D278). The palette holds no red and no green.
- Today's price comes from the price archive, with its own age (D225). The screen never fetches on
  its own.
- A name with no reading shows no figure and never a zero. The count of names with no reading is
  stated on the same screen as any total.

### Unsold stock: value over time (BUILT)

For cards still held, value them at the market and show that value moving (D236).

- The position is the SKU. Every copy is fungible and no order claims one (D212).
- Quantity comes from the card table's own state, never from the count the marketplace holds. That
  count is a stale mirror until the next reconcile.
- Every mark carries its age. A total carries the count of names it could not mark.
- **Sealed stock has no card record, so it has no quantity in the card table.** Revenue is
  dominated by sealed product, and unsold sealed stock cannot be valued. It is a named, counted gap.

## 2. Refunds

Three layers, in order of what they cost to reach.

- **Already on the wire (BUILT, D225).** `closed_reason` rides on every line's progress, and its
  value `not_shipping` means refunded or cancelled. The screen subtracts it. The limit is stated on
  the screen: the operator records the value when closing a line during fulfilment. It is not the
  marketplace's word, so coverage is a habit and not a guarantee.
- **Dropped at the boundary (NOT BUILT).** `refunds` is a field the marketplace sends, and
  `server/order_transport.py` drops it on purpose. Recovering it widens a security boundary. That
  needs the owner's word, named for that field. No session may do it alone.
- **Never modeled (NOT BUILT).** A refund, a return and a partial cancellation have no state in the
  data model. The terminal status vocabulary holds three words and none is a refund. If the feed
  reported one, it would be stored verbatim and read as open. Someone must first look at what the
  feed reports on a refunded order, before anyone designs a state for it.

## 3. The per-product view (BUILT)

`#/product` (D227) is one page per product, deep linkable by `?sku=`. It reads
`store/pricearchive.py` first and falls back to a live read through `pipeline/pricehistory.py` only
for a SKU the archive has never swept. It never writes and never starts a sweep. The route is
`server/pipeline_routes.py:do_product_history`, the read is `pipeline/productview.py`, and the
screen is `app/src/ProductHistory.tsx`. `scripts/product-history-selftest.py` proves it and is not
wired into `make check`, following `scripts/pricearchive-selftest.py`.

It is off-nav. The route's own SKU field is the control a person finds without a query string.
`docs/specs/sales-findings.md` holds the twelve constraints. Three decide the design:

- **The market series and the owner's fills are two kinds of observation.** The series is an
  aggregate of many transactions. The fills are exact. They are never one continuous series.
- **Bucket width depends on when the report is read and not on when the sale happened.** The same
  sale sits in a one-day bucket today and a seven-day bucket months later. Precision decays for a
  fixed fact, so the width is stated beside any comparison.
- **Nothing reaches back more than 357 days**, and the chart states the date its own history begins.

### The posted-price view (OPEN: two placements, the owner picks)

DEBT68. `price_postings` (D243) records every posted price, one row per SKU per press. A view
is gated on one SKU holding a second posting, because one posting is a point and draws no
history. Measured on the owner's store: 103 rows over 103 distinct SKUs, so the gate is closed.
Build either option below only after the gate query reads rows above distinct SKUs. Both
options need one new read route over `store/postings.py`, one client function in
`app/src/server.ts` and one wire type in `app/src/types.ts`. Neither writes.

Rules both options keep: a posted price is a third kind of observation, never joined to the
market line or the fills (D278). It is drawn as a held step, because a price stays until the
next press. Money uses `.bn-money` (D221). Kit pieces and `--bn-*` tokens only. A chart or
table holds its size from first paint (D313, nothing moves unless the person moved it).

**Option A: a third series on the product chart.** Each range chart on `#/product` gets a dashed
ink step line with one hollow square per posting. The legend gains one entry. The price axis
widens to include postings.
- Gain: asked price sits against the market line and the sale diamonds, so "I asked too high" is
  one glance. It is per SKU, the grain of D212, and reuses the page D227 argued for.
- Loss: it answers one product at a time. The owner must already know which SKU to open. It adds
  a fourth mark to four stacked charts, and a flat step line under a spiking market line reads as noise.

**Option B: a Sales section.** A section on `#/revenue`, below the sold products, titled
"What you asked". One row per re-priced name: posts, first asked, latest asked, change, average
sold at. Each name links to `#/product`.
- Gain: it answers "which cards did I re-price, and did it help" across the store at once. It
  needs no chart and no new mark.
- Loss: it shows the ends of a history, not its shape. It sits on a gross-revenue screen (D214)
  and so risks reading as a profit claim. The period control then needs a rule for posts outside it.

Both can ship. B finds the SKU and A shows its shape. Mock images were made on demo data with
fabricated postings. They are not part of the repo.

## 4. The archive (BUILT)

The price-history source has a hard ceiling of 357 days. Everything older is gone, and everything
not captured now ages out on the same schedule. This was the one item where delay cost something
nobody could recover.

The pattern is the readings table and its adopt command. `store/pricearchive.py` is the table,
`pipeline/pricearchive.py` is the walk, and `cli/cmd_pricearchive.py` is the press
(`pkmnscan archive sweep [--write]` and `pkmnscan archive show [--sku ID]`).

- **Buckets are keyed by `(sku, range, start)` and never by width.** The ranges overlap, and
  `semiannual` and `annual` are both seven days wide, so a width-only key would collide two
  independent observations. D278 forbids that, and D219 argues the key.
- **The archive never deletes a row.** A bucket that a later sweep does not mention stays as it
  was. It may have aged out of the source, or its SKU may have fallen outside a narrower pass. This
  is the
  opposite of `readings adopt`, which is a full replace.
- **The sweep's subject is every distinct SKU that `cards` has ever recorded.** Sold and held both
  keep the row (D26, D134).
- **The schedule is deferred.** The sweep is a press a person runs. A timer reverses D278's
  statement that this reader cannot fire on its own, and that reversal needs its own argument.

## 5. Ride-along defects (BUILT)

Six defects rode along with D225 and are fixed:

- the comparison sentence's lead
- order numbers clipping at 390px
- the product name column's missing height cap
- the fifth period option wrapping alone
- the missing `bn-stagger` on the rows
- the verdict figure with no weight of its own

Two items were questions and not defects, and they stay the owner's. Money in a table is mono, and
D221 (money stays mono) settles it. The month chart's known faults stay, by the ruling above.
