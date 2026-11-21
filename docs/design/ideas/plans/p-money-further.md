# p-money-further

Lot Tag works. It needs three fixes first: lot cost gets spread after the paid ID step (cards have no market value at capture), the existing 3,600 cards need to be tagged by box and section, and the Fulfiller's pull decides which copy sold.

**Premises.** All are from the brief. I could not check any of them because the brief barred file reads.
- P1 ~3,600 cards, 6 long boxes, 9-22 sections; rig captures 1,300/h with box, section, position (brief). Unknown.
- P2 A paid step identifies each card; listings go up as spreadsheet files; orders come back as exported files (brief). Unknown.
- P3 Cost is spread "by market value at capture" (earlier plan). **Fails by the brief's own order**: market value exists only after the paid ID step. Spread when the lot is fully captured and priced.
- P4 A sale maps to one physical card (implied). **Unknown**: if two copies of one listing come from different lots, the order file cannot say which sold. The Fulfiller's pull decides it.
- P5 Order exports carry fees and postage, so "recovered" can be net (implied). Unknown.
- P6 Current stock has no lot (implied by "cost unknown"). Likely holds. So a v1 without tagging after the fact shows almost all stock as unknown.
- Glossary terms (lot, capture run, allocation): unchecked, since I could not read the glossary. There is no test or merge change, so the test-practices and merge-practices records do not apply.

**1. Core loop**
1. Buy: the owner adds a lot. It records amount paid (with shipping and tax), date, seller, and an optional expected card count.
2. Capture: the feeder screen has a "current lot" picker. It stays set for the run, with one tap to switch. No lot means "cost unknown." Existing stock is tagged by a box-and-section range.
3. Identify and price: when every card is priced and the lot is marked "capture done," the spread runs once. It stores the method, the market-value snapshot and the result as version 1.
4. Sale: an order comes in, the Fulfiller pulls a card, and that physical copy is marked sold. Its cost of goods is its stored share. Net proceeds count toward "recovered."
5. The lot page over months shows paid, recovered, net, cards left with their cost, a recovery chart, and the break-even date. The date is actual once reached. Before that it is a projection from the sales rate, or "too few sales" under a minimum count.
6. Year end shows cost of goods sold, stock at cost, and the share of stock with unknown cost, by count and by value. Kept, traded and lost cards are separate lines. "Close year" pins those figures.

**2. Screen states**
- New lot: "$400 paid · 212 of ~300 captured · 41 unpriced · cost not yet spread."
- Partway recovered: "$230 of $400 back (58%) · 171 left, $170 cost on shelf · break-even ~March."
- Broke even: "Broke even 14 Jan · +$86 since." The cards left keep their cost. The screen never calls them free.
- No lot: a "cost unknown" badge. The card is left out of profit. Every total reads "covers 2,950 of 3,600 cards (82%)."
- Split across runs: lists each run with its date and count. The spread is marked "provisional" until "capture done."
- Kept or traded: sold, kept, traded, lost and left each get a count and a cost. Kept cards leave stock at cost; they are not a sale and not a loss.

**3. Spreading the cost honestly**
- Default method is a floor plus market value: each card gets a small floor, such as $0.05. The rest of the cost is spread by market-value share, which fixes the "cheap cards look free" risk.
- Other methods: equal per card, and a manual cost on one card with the rest re-spread.
- Each card shows "$1.84 = 4.6% of $40 lot, by market value on 3 Feb (v1)." The snapshot is never re-priced.
- Spread versions are only ever added, never edited. A method change writes a new version for unsold cards only. Sold cards keep the version in force at their sale, and closed years stay pinned. The year view shows a "restated: −$12" line instead of silently changing figures.

**4. Smallest version worth shipping**
- The lot record, the capture picker, tagging by box-and-section range, the floor-plus-market-value spread stored as v1, and "cost unknown" plus coverage on every total.
- A lot page with paid, recovered, cards left, and the actual break-even date only.
- Deferred: projections, kept and traded handling, the year-end view, and a screen to change the method. The version store ships in v1, so any of these can be added later without rewriting history.

**5. Measure**
- The share of net sales proceeds over the last 60 days that comes from cards with a known cost. Target: 80% or more within 60 days of launch. This tests whether owners tag at all, including old stock.

**6. Questions only the owner can answer**
1. Is the year-end view for tax filing (then a method change applies only from the next year) or just for your own insight?
2. Can the current ~3,600 cards be traced to lots by box or section from receipts, or should they stay "cost unknown"?
3. In a trade, should the incoming cards cost what the outgoing cards cost you, or the market value of what you gave?

I wrote no files.
