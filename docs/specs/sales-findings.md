# Sales: findings and constraints

**Status: OPEN FINDINGS AND STANDING RULES.** Five independent reviews of the Sales screen produced
this file. D214 (sales shows gross, never profit) records why the screen exists, and D217 (sales
sorts, filters and deep links) records what made it interactive. D278 (one product view, two
frames) holds the price-history rules that every chart inherits. `docs/specs/sales-plan.md` holds
what was built. Defects the plan fixed are gone from this file. The findings below are still open,
or were not re-checked against the tree, and each says which.

## 1. Findings still open

None is a data error. Each could mislead a decision.

- **The month chart hides a gap month.** A bucket exists only for a month that carries a sale, plus
  the month that holds today. The geometry function spaces points by array index, so two months on
  either side of an empty one draw as neighbors. Its break logic was written for a price series on a
  fixed calendar grid, and it cannot fire on a variable list of populated months. The owner ruled
  that the chart stays and its faults are marked, so a session may not fix this without asking.
  *Not re-checked: the screen has drawn bars since.*
- **The chart rescales itself.** The geometry normalizes to the lowest and highest value in view, so
  slope carries no absolute meaning. At two or three buckets, a reviewer saw the line draw a
  full-height plunge or a spike and a cliff. The low bucket was the unfinished current period.
  *Not re-checked.*
- **Percent change has a zero guard and no floor.** A prior period of five cents against a current
  fifty dollars would draw as a five-figure percentage at the weight of any other figure. D278 sets
  the convention: an anchor carries one weight and a bound carries another. *Not re-checked.*
- **Drilling into the unfinished period loses that fact.** Selecting the current month narrows the
  product table, and nothing in the table or the filter chip says the month is still running.
  *Not re-checked.*
- **The tests leave the arithmetic unguarded.** No assertion reads the chart's rendered geometry. No
  fixture carries a gap month or an order of more than one line. The order-count de-duplication
  therefore runs only on data that cannot expose a fault in it. *Not re-checked.*
- **Two plausible faults were never measured.** Preset comparison windows may overlap the current
  window by one to three days when a period closes. The previous window's end comes from elapsed
  milliseconds against a calendar-anchored start. Gross accumulates in floating point over
  about 1,268 currency additions with no integer-cent sum. No discrepancy has been seen.

## 2. Rules the reviews left standing

- **Cost basis.** A lot with unknown basis is labeled unknown. It is never assumed to be zero, and
  it is never blended into one aggregate gain beside lots whose basis is known. Every historical lot
  in this store would be unknown. Blending is the likeliest way this product lies to its owner.
- **A comparison with the market at the time of sale measures pricing quality and never performance.**
  It is blind to acquisition cost, so it must not be labeled performance or gain, and it must not sit
  near the word revenue.
- **Marking unsold stock to market carries the age of each mark and a count of names with no mark.**
  Both sit on the same screen as any total. The screen already does this for lines it drops.
- **The screen groups by when an order was placed and not by when money arrived.** Beside a
  marketplace's annual statement, that timing convention reads as a software fault, so it must be
  stated.
- **Nothing here shows a position, a quantity held or a basis.** It is a trade blotter and not a
  portfolio view. Language elsewhere must not edge toward a register it has not earned.

## 3. Constraints on the per-product view

The view shows what a product has been selling for and marks the owner's own sales on that line.
The owner's sales are exact fills, each with a price, a quantity and a date. The market series is an
aggregate, and each bucket describes many transactions with a market figure, a low, a high and a
quantity. They are two kinds of observation. D227 (product history is its own route) and
`pipeline/productview.py` build on these twelve rules.

1. The market series and the owner's fills are never one continuous series. Use different marks and
   a legend.
2. Carry the aggregate's own spread and never discard it. D278 measured a band 48% of the estimate
   wide on a real card. One number that compares a fill with a bucket claims a precision the source
   refuses.
3. Direction is a sign and a word and never a color. The palette holds no red and no green.
4. A bucket with no price breaks the line and is never interpolated across.
5. The chart states the date its own history begins. A year of local archive is not a year of market
   history, and nothing backfills the difference with an assumption.
6. A sale older than 357 days has no market data. What draws for it must be visible and say so.
7. Bucket width depends on when the report is read. One sale sits in a one-day bucket today and a
   seven-day bucket months later, so the width is stated.
8. Weekly buckets are stamped at the start of their week. Matching a sale to a bucket therefore
   carries a boundary ambiguity of several days beyond the 87-day mark.
9. A counterfactual priced at one figure assumes that the market absorbs the whole quantity at it.
   The same source disproves that, bucket by bucket, through its quantity field.
10. The current price feed is at product and printing level and not at condition level. A
    condition-specific sale compared with a blended figure is not the same card.
11. Archive buckets are keyed so that overlapping ranges never merge. One day is a one-day bucket in
    one range and part of a seven-day bucket in another. Those are two facts (D219).
12. The sweep costs about one second per cold name. A sweep over every sold or held name is a
    press and not a page load.

## 4. Open for the owner

1. **Refund disclosure beyond the operator's own closes.** Layers 2 and 3 in the plan's section 2
   need the owner's word.
2. **An export.** Every other money surface here produces a file. This is the one screen whose figure
   a tax preparer would want, and it has none.
3. **Whether the chart is deleted, repaired or left alone.** The standing ruling is to leave it. One
   review argued for deleting it, because it duplicates the list beneath it and carries no axis. If a
   shape is wanted, a proportional fill behind each row's own value inherits the row's real scale.
4. **Whether cost basis is ever captured, and at what grain.** The reviews agree that unknown basis
   must be labeled and never blended, whatever grain is chosen.
5. **A scheduled archive sweep.** The owner asked for one. It reverses D278's statement that the
   reader cannot fire on its own, and that needs its own argument.
