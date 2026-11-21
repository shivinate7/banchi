# p-money

**1. Name:** Lot Tag at the Feeder

**The idea:** Every batch that goes through the capture rig carries a purchase lot: what was paid, when, and from whom. The cost is spread across the lot's cards in proportion to their market value at capture. A card with no lot is shown as "cost unknown", never as zero. Profit appears only where cost is known, and every total says how much of the stock it covers.
**Who it helps:** The owner. It also helps at tax time, because the cost of goods sold and the year-end stock value come out of it directly.
**Why now:** Capture is the cheapest moment to record cost. Receipts get lost, and buying cost cannot be rebuilt later. With 3,600 cards the backlog is still small enough to tag by lot or write off as "pre-ledger".
**Rough shape:**
- Before a batch runs, the owner picks or creates a lot: price paid, source and date. It takes one tap, and "no lot" is allowed.
- A sold card shows sale price, fees, a share of the postage, supplies and its lot cost. The result is net profit, or "net before cost" when the lot is unknown.
- A lot page shows money paid, money recovered so far, cards left and the date the lot broke even, if it has.
- The year-end view shows cost of goods sold, stock at cost and how much stock has no known cost, as a percentage.
**Risk:** Spreading cost by market value makes cheap cards look free and costly cards carry the lot, so the method has to be stated on screen.

**2. Name:** Shelf Rent by Section

**The idea:** Treat each box section as rented shelf space. Each one is scored on the cash tied up in it (at cost, or at market when cost is unknown), what it sold in the last 90 days, and how fast its stock turns. Sections follow set order, so the result also tells the owner which sets are worth buying again.
**Who it helps:** The owner, when deciding what to buy and what to clear out. The Fulfiller indirectly, because there are fewer dead boxes to dig through.
**Why now:** About 3,600 cards against a median of 3 orders a day means most cards sit unsold for months. With six boxes it is still cheap to consolidate, retire a set or bulk out a section before a seventh box is bought.
**Rough shape:**
- A grid of boxes and sections, each showing cash tied up, sales per month and days of stock left.
- A "dead weight" list: cards with no sale in N days at the current price. Each offers to reprice, bulk-sell the section as a lot or leave it.
- A forecast line: at the current sell rate, this section clears in about N months.
- Slabs are tracked on their own, so one costly card cannot hide a dead section.
**Risk:** At 3 orders a day, 90-day sales per section are small samples. Each score needs a "too few sales to judge" state.

**3. Name:** Net per Order, Including Hands

**The idea:** Each order is broken down: sale price, minus marketplace fees, postage and supplies for its shipping method, and the Fulfiller's minutes at their hourly rate. The time comes from start and finish taps on the pick list. This shows the order size below which a sale loses money, and whether the Fulfiller's hours cover their cost.
**Who it helps:** The owner, when setting minimum prices and shipping rules. It also gives an honest answer on the Fulfiller's pay.
**Why now:** Most cards sell for a few dollars, so a single $0.50 card can lose money once fees, a mailer and five minutes of pulling are counted. Peak days of 39 orders multiply that loss. Finding the threshold now is cheaper than finding it at 10,000 cards.
**Rough shape:**
- The Fulfiller taps "start" and "packed" on each order. Nothing else changes in their work.
- An order list with a net figure on each row, flagged red, amber or green, and a breakeven line marking the order size that pays.
- A weekly line: Fulfiller hours, their cost, and the margin from the orders they shipped.
- A what-if control: raise the floor price to $X and see how many past orders it would have changed.
**Risk:** Timing a person can feel like being watched. Show the figures per order, not per person, and agree on it with the Fulfiller first.

**Bet:** I would build Lot Tag at the Feeder first. Cost data is cheapest to record at capture and is lost for good once receipts go missing. Directions 2 and 3 give stronger answers once cost basis exists, and until then they can only report net before cost.
