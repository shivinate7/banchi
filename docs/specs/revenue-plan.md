# Sales: the build plan

**Recorded 2026-09-19.** This is the plan the owner settled by interview on 2026-09-19. It
supersedes nothing. Read `docs/specs/revenue-next.md` first. That file holds the findings. This
file holds what to do about them.

**Refunds (§2) and sold-cards then-against-now (§1, first half) are BUILT**, 2026-09-19,
D225. Six of the §5 ride-along defects rode along with them.
Unsold-holdings value-over-time (§1, second half), the per-product view (§3) and money
typography (§5's open question) remain not built.

Build order is deliberately not fixed here. The owner asked to choose it when the work is picked
up.

## The owner's rulings

Four questions were put. Three were answered. One was held.

**On hindsight against today's prices: build both, as two separate things.** The owner's words:
they want to see, on cards already sold, how much was gained or lost by selling then rather than
now. Separately they want unsold holdings valued over time. These are two features and not one
headline. A reviewer argued the first should be refused outright. The argument was that a banked
profit drawn as a loss trains the reader to hold instead of sell. That argument is recorded in
`docs/specs/revenue-next.md`. The owner has read it and ruled against it. Build it, with the
honest framing in section 1.

**On the month chart: mark the faults known and leave it alone.** No repair and no deletion. The
three faults are recorded. A future session may not treat them as a defect to fix without asking.

**On refunds: the data exists.** The owner said refunded orders appear in the export. That turned
out to be right in three separate ways, which section 2 sets out.

**On build order: ask again at the time.**

## 1. The two value questions

These are separate features with separate rules. Nothing may merge them into one figure.

### Sold cards: then against now

**BUILT 2026-09-19 (`D225`).** For a card already sold, compare the price it went for against what the market says today.

The owner's own sales are exact fills. Each carries a price, a quantity and a date. There are
1,268 of them. That is a real measurement and not an estimate. This is the half that makes the
feature defensible.

Rules that govern how it is drawn:

- It is a market observation and never a profit or a loss. No label may say gain, loss,
  performance or missed. The card was sold and the money was taken.
- It is blind to what the card cost. That fact belongs next to the figure. A card bought at two
  dollars and sold at eighteen against a twenty dollar market is a large gain. This figure draws
  it as a shortfall.
- Direction is a sign and a word, never a color. D62 sets this. The palette holds no red and no
  green.
- Today's price comes from the readings table, drawn with its own age. A press refreshes it. The
  screen never fetches on its own.
- A name with no reading shows no figure. It is never shown as zero. The count of names with no
  reading is stated on the same screen as any total.

### Unsold stock: value over time

For cards still held, value them at the market and show that value moving.

- The position is the SKU. D212 settles this. Every copy is fungible and no order claims one.
- Quantity comes from the card table's own state. It never comes from the count of what the
  marketplace holds. That count is a stale mirror until the next reconcile.
- Every mark carries its age. A total carries the count of names it could not mark at all.
- Sealed product has no card record, so it has no quantity in the card table. This is the open
  problem. Revenue is dominated by sealed product. Whether unsold sealed stock can be valued at
  all is unresolved. It must be measured before this is designed.

## 2. Refunds, which are reachable after all

**The first layer is BUILT 2026-09-19 (`D225`).** The second and third stay as
recorded below.

Three layers, in order of what they cost to reach.

### Already on the wire and ignored

`closed_reason` rides on every line's progress, in the same payload Sales already fetches. Its
value `not_shipping` is described in the store's own words as refunded or cancelled, nothing will
go. `OrderCloseReason` carries it to the browser today.

`Revenue.tsx` does not read it. The only two matches for the word progress in that file are prose
about an in-progress period.

**This is a real subtraction available with no new data and no boundary change.** It needs no new
route. It is the cheapest correctness fix in either file.

Its limit must be stated on the screen. The value is recorded by the operator when a line is
closed during fulfilment. It is not the marketplace's word. Coverage is therefore a habit and not
a guarantee.

### Dropped at the boundary

`refunds` is a field the marketplace sends. `server/order_transport.py` names it in the list of
fields the five-field allowlist drops. The data exists and this repository refuses it on purpose.

Recovering it widens a security boundary. That needs the owner's word, named for that field
specifically. It is not a change any session may make on its own.

### Never modelled

A refund, a return and a partial cancellation have no state anywhere in the data model. The
terminal status vocabulary holds three words and none of them is a refund. If the feed ever
reported one, it would be stored verbatim and read as open.

Closing this needs a measurement first. Someone must look at what the feed actually reports on a
refunded order. That comes before anyone designs a state for it.

## 3. The per product view

**BUILT.** `#/product` (D227). One page per product, deep linkable by
`?sku=`. It reads `store/pricearchive.py` first. It falls back to a live read through
`pipeline/pricehistory.py` only for a SKU the archive has never swept. It never writes and
never triggers a sweep from the screen. `server/pipeline_routes.py:do_product_history` is
the route. `pipeline/productview.py` is the read it calls. `app/src/ProductHistory.tsx` is
the screen. Proved by `scripts/product-history-selftest.py`, not wired into `make check` —
`scripts/pricearchive-selftest.py`'s own precedent.

Off-nav rather than linked from `#/revenue`: that screen was being edited by a parallel
branch. The decision entry argues the route-versus-lens question. It also argues why the
link from `#/revenue` is deferred rather than built. The route's own SKU field is the
control a person who lands here without a query string actually finds.

One page per product, deep linkable. It shows what a product has been selling for. It marks the
owner's own sales on that line.

The twelve constraints on this view are recorded in `docs/specs/revenue-next.md`. They are not
repeated here. Three of them decide the design and are restated, because a builder will otherwise
miss them.

**The market series and the owner's fills are two different kinds of observation.** The market
series is an aggregate of many transactions. The fills are exact. They may never be drawn as one
continuous series.

**Bucket width depends on when the report is read, not on when the sale happened.** The same sale
sits in a one day bucket today and a seven day bucket months later. Reported precision decays over
time for a fixed fact. The width must be stated beside any comparison.

**Nothing reaches back more than 357 days.** The chart states the date its own history begins.

## 4. The archive

**BUILT.** The price history source has a hard ceiling of 357 days. Everything older is
already gone. Everything not captured from now on ages out on the same schedule.

This was the only item in either file where delay costs something nobody can recover later.

The house pattern is the readings table and its adopt command, applied here.
`store/pricearchive.py` is the table. `pipeline/pricearchive.py` is the walk.
`cli/cmd_pricearchive.py` is the press (`pkmnscan archive sweep [--write]`,
`pkmnscan archive show [--sku ID]`).

Buckets are keyed by `(sku, range, start)`, **not** by width. The ranges overlap. `semiannual`
and `annual` are both seven-day-wide, so a width-only key would collide two independent
observations. That is exactly the collision D62 forbids.
D219 argues the key in full.

The archive never deletes a row. A bucket a later sweep does not mention is left exactly as it
was. That covers two cases: it aged out of the source, or that SKU fell outside a narrower
pass. This is the opposite of `readings adopt`, which is a full replace. The two entries' own
module docstrings say why each shape is correct for its own table.

The sweep's subject is every distinct SKU the `cards` table has ever recorded. Sold or held,
neither state deletes the row (D26, D134).

The owner asked for a scheduled sweep. The schedule is still deferred. The sweep is a press a
person runs. A timer reverses D62's own statement. D62 says this reader cannot fire on its
own. That reversal needs its own argument, which nobody has made.

## 5. Defects to carry into whichever change comes first

**All six below are BUILT 2026-09-19**, riding along with `D225`.

- ~~The `lead` string in `compareLine` attributes `So far` to a closed period. Fix the string. Add a
  test at the default period against a populated prior window.~~
- ~~Order numbers clip in the middle of the string at 390 pixels, in the per order drill down.~~
- ~~The product name column has no height cap, so numeric baselines drift down the table.~~
- ~~The fifth period option wraps onto its own row and sits alone at 390 pixels.~~
- ~~`bn-stagger` is absent from the month rows and the product table. The house rule is written and
  the mechanism exists.~~
- ~~The verdict figure carries no weight of its own. Pricing wraps the key figure of every verdict
  in a strong tag. One tag, no words.~~

Two items are questions rather than defects. They are not for a builder to settle.

- Money in a table is set in mono. `CLAUDE.md:321` forbids it. A comment at `RunPanel.tsx:226`
  defends it. One of the two has to give way and that is a repository level ruling.
- The month chart's three faults are known and the owner ruled that they stay. A session may not
  quietly fix them.

## 6. What to ask the owner when this is picked up

1. Which of the four bodies of work comes first.
2. Whether unsold sealed stock can be valued. Measure whether sealed product has any quantity this
   store can count, before asking.
3. Whether the `refunds` field is let through the boundary, named for that field.
4. Whether money in a table stays mono.
