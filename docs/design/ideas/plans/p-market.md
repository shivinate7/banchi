# p-market

Three directions follow, through the price and market-timing lens. I read no files, as the brief asked.

**1. Name:** Price policies, not prices
**The idea:** Each card gets a pricing rule instead of a hand-set price, and the rule matches what the card is worth. Cards under a few dollars follow the market inside a fixed floor and ceiling and never ask for attention. Mid-value cards come up for review together, once a week, on one screen. Slabs and the few high-value cards get a human decision with their recent sales beside them.
**Who it helps:** The owner. Thousands of price calls become a handful of policies and a short exception list.
**Why now:** With about 3,600 cards, a weekly price check by hand is either thousands of glances or a skipped job. The cheap cards also don't earn the minute a person would spend on them.
**Rough shape:**
- The owner sets three or four bands by value, each with its own rule, for example "follow market, never below the floor" or "hold, ask me".
- An exception queue lists only the cards whose rule wants a large move or whose value crosses a band.
- Each exception is one tap: accept, hold, or move the card to a different band.
- Repricing goes out as one upload file per batch, not one edit per card.
**Risk:** A bad rule misprices hundreds of cards at once, so each batch needs a preview and an undo.

**2. Name:** Sell-speed feedback and markdown ladder
**The idea:** The order exports already show how long each listing sat before it sold. A card that sells within hours was probably underpriced, so its siblings (same card, other condition, same set) get nudged up. A card unsold after N weeks steps down a ladder, like a retail markdown, until it reaches a floor. The floor is set by what the card costs to pull, pack and ship, not by the market.
**Who it helps:** The owner, who gets margin back on fast sellers. The Fulfiller, who stops making trips for cards that lose money.
**Why now:** At a median of 3 orders a day, most cards wait months, so the time a card sits is the strongest price signal this store has. It is free, because the order files already exist.
**Rough shape:**
- Each card shows its age on the shelf and a "sold fast / normal / stale" mark.
- A weekly ladder step proposes cuts on stale cards and raises on siblings of fast sellers.
- Cards that hit the floor are flagged as "below pick cost". The owner can bundle them, sell them as bulk lots, or delist them.
**Risk:** At 3 orders a day the sample is thin, so a few lucky fast sales could push up prices that should stay put.

**3. Name:** Set clock for list timing
**The idea:** Singles from a newly released set usually fall for weeks as supply floods in. Older sets can jump on reprint news or tournament results. The store already knows each box section's set before the paid identify step runs. It can therefore hold sets that are still falling and spend identify money first on sections whose set prices are high now.
**Who it helps:** The owner. It decides when to list, and also when to pay for identify.
**Why now:** Identify costs money per card and runs in batches, so the order of the batches is a real decision. Cards are already sorted by set, which makes set-level timing cheap to act on.
**Rough shape:**
- One row per set shows its age, price trend over 30 and 90 days, and a "list now / wait / spiking" mark.
- The next identify batch is suggested from the sets marked "list now" or "spiking".
- A spike alert covers the high-value tier only. It suggests raising the price or holding the card, and never cuts during a spike.
**Risk:** Market price feeds lag and can be noisy, so "wait" can turn into cards that never get listed.

**Bet:** Build Price policies first. It turns about 3,600 price calls into a few rules. The markdown ladder and the set clock then become rules that plug into it, not separate tools.
