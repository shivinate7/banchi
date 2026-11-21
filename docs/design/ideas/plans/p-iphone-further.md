# p-iphone-further

# Card-Show Pocket Verdict

**1. The core loop**
1. **Before leaving home.** The owner taps "Going out" on the phone. It copies a snapshot of their store into the phone's own storage: what they hold, how many copies, how fast each card sold in the last 90 days, recent sale prices, and the fee rates. They can also add a cash budget for the day. After that the phone needs no signal.
2. **At a table.** They hold one card up to the camera. The phone reads the set code and card number printed on the card, so it does not use the paid identify step. A verdict shows within a second, and a haptic matches it: one firm tap for BUY, a soft double tap for PASS.
3. **Deciding.** The verdict is one large number, BUY UNDER $X, with one line of reasons under it, such as "sells in about 3 weeks, you have 0". They haggle against that number.
4. **Logging a buy.** If they say yes, they swipe up and enter the price they paid. The card joins a running "bought today" list with a total spent and a total expected margin. The budget shown on screen goes down.
5. **A binder or a lot at one price.** They tap "Lot", enter the asking price, and sweep the camera over the cards one by one, or page by page in a binder. The phone adds up a lot value as they go and shows a lot verdict at the end.
6. **Back home.** The phone syncs. The "bought today" list becomes an intake batch for the next capture run, already priced. The paid identify step then runs only on the cards the phone could not name.

**2. The phone states**
- **BUY UNDER $4.20.** The screen is green, with the number large. Under it: "sells in about 18 days at $6.80 · you have 0".
- **PASS.** The screen is grey. Under it: "best case $0.90 after fees, below your floor". A PASS never shows a buy price, so a low number never looks like an offer.
- **TOO MANY.** The screen is amber. It reads "You have 5, about 7 months of sales on hand", and the buy price for one more copy drops or disappears. This is the state that stops a rare-looking card they already hold in bulk.
- **NOT RECOGNISED.** The screen is outlined, with no number. The phone offers to type the set and number, or to "Snap for later": the photo is saved, and the card is identified and priced at home. It never guesses a price.
- **SLAB.** The phone reads the grading company and grade from the label and shows "PSA 9 · BUY UNDER $X · from 6 graded sales". If it has fewer than about 3 graded sales, it shows "thin data" with the range instead of a number.
- **LOT: $80 asked.** One bar fills as each card is swept. A running line reads "worth $112 to you · 31 named · 4 unknown counted at $0". It ends with BUY or PASS for the lot, and the 3 cards that carry most of the value are listed, so the owner can offer for just those.

**3. How the buy-under price is worked out**
- It starts from what the card actually sold for in this store's own recent sales. Where the store has too few sales, it uses the marketplace's recent sales, marked lower in trust.
- It takes off what the marketplace keeps: its percentage, the payment fee, and this card's share of the per-order costs (sleeve, envelope, postage), using the store's own average cards per order.
- It takes off what it costs the owner to handle the card at all: capture, the paid identify, picking and packing. This fixed cost is why most cheap cards come out PASS.
- It discounts for waiting. A card that sells in a week keeps nearly its full value. A card that takes six months loses more, because cash is tied up and prices drift.
- It counts copies already on hand. Each extra copy waits behind the ones already in the box, so it gets a longer wait and a lower value.
- Last, it takes off the owner's target margin. What is left is the most they should pay.

**4. The smallest first version worth shipping**
- It handles single cards only, read by the set number with typing as the fallback, plus the BUY UNDER, PASS and TOO MANY states, all from the offline snapshot.
- Buys are logged to a list that comes home as an intake batch.
- Slabs, lots and binder sweeps wait for the second version. Lots matter most at shows, but they only work once the single-card verdict has earned the owner's trust.

**5. One measure that it worked**
The share of cards bought on a "BUY" verdict that sold within their predicted wait at or above their predicted price. A useful target is above 70% across the first two shows. If the share is low, the formula is wrong. If it is high but they bought little, the margin is set too tight.

**6. Questions only the owner can answer**
1. What margin and what longest wait make a buy worth it to them? For example, 40% within 90 days.
2. Is the phone ever allowed to reach the home Mac from a show, or must it work fully offline? Connecting live would allow fresher prices, but it opens the store to the outside.
3. In a lot, should an unrecognised card count as $0, or at a flat bulk rate they choose?
