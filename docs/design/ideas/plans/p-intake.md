# p-intake

**Bet:** I would build Skip the Sort first, because sorting by hand is the hidden cost behind "zero attention per card".

**1. Name: Skip the Sort**
**The idea:** The rig already records box, section and position for every card. So once a card has been captured, sorting it by set and number does not help anyone find it. Let a whole collection go into the rig in the order it arrived, and let the store give each card its location.
**Who it helps:** The owner, who now spends hours sorting by hand before the rig runs. The Fulfiller also gains, because the walk-order route already finds cards by position, not by set.
**Why now:** Collections and shoeboxes are where intake grows. At 1,300 cards an hour, the rig is faster than any person who sorts first.
**Rough shape:**
- An intake mode labelled "unsorted lot" that does not expect set-and-number order.
- When a lot is captured, it shows a summary: cards per set, duplicates, and how many it could not identify.
- An optional "re-home" list moves cards into existing sorted boxes only where that makes picking shorter.
**Risk:** The sort-order check on identification no longer works, so another way to catch wrong identifications is needed.

**2. Name: Worth-It Gate Before Identify**
**The idea:** Most of a bought collection is worth less than its identify cost plus listing fees. Before the paid identify step, a cheap pass sorts each card into "identify and list" or "bulk bin". It would use rarity symbol, foil, or set symbol from the photo. Bulk cards are then sold by count or weight and never get a listing.
**Who it helps:** The owner's margin. It also keeps thousands of near-worthless cards out of the long boxes the Fulfiller works from.
**Why now:** Identify costs money per card, and whole-collection buying multiplies that cost on the cards least likely to sell.
**Rough shape:**
- A threshold the owner sets, for example "identify only if likely worth more than the identify cost plus a margin".
- A bulk bin that the store tracks as one item with a count, not card by card.
- A spot-check screen showing what the gate sent to bulk, so the owner can catch a misread card.
**Risk:** A valuable card that looks like a plain common goes to bulk unseen.

**3. Name: Condition at the Door**
**The idea:** A collection or trade-in holds played cards, not cards fresh from packs. From the capture photos, flag cards with visible wear, such as whitened edges, creases or scratched foil. Send those to a condition review instead of listing them as Near Mint by default.
**Who it helps:** The owner, through fewer returns and fewer bad reviews. The Fulfiller, who no longer handles complaints about a card that "isn't NM".
**Why now:** Buying collections changes how stock arrives. Sealed product was pack-fresh; collections bring mixed condition into a pipeline built to give each card no attention.
**Rough shape:**
- Each flagged card shows its photo next to a reference Near Mint image, with one-tap buttons for each condition grade.
- A per-lot condition summary that feeds back into how much the owner pays for the next collection.
- Cards worth sending for grading are marked at intake, not found by chance later.
**Risk:** False flags bring back attention per card. The flag rate must stay low or the owner will start ignoring it.

**Why Skip the Sort:** It removes the biggest hidden labour in intake, and the store already knows where each card sits, which is what makes it safe. Worth-It Gate is a close second, because it saves money from the first collection, and the two fit together: an unsorted lot can pass through the gate at capture time.

I did not check any of these against the code or the decision records, because the brief said not to read files.
