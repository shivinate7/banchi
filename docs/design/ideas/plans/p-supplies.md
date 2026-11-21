# p-supplies

Premises: not checked against the code, because the brief forbids reading files.

**1. Name:** Pack recipe on every pull slip
**The idea:** Each order shows its full packing build, worked out from the cards it holds, before the Fulfiller starts. The build covers the protection (sleeve, toploader, team bag or slab sleeve), the envelope or mailer, and the postage: how many stamps, or a tracked label. The Fulfiller follows it and makes no judgment calls.
**Who it helps:** The Fulfiller, who is non-technical and today guesses about weight and rigidity. The owner, who stops paying for returned mail and buyer complaints.
**Why now:** The store already knows each card's value and whether it is a slab. Weight comes from card count. On a 39-order peak, that guesswork is where the errors happen.
**Rough shape:**
- Each order card shows icons: "1 sleeve + 1 toploader, plain envelope, 1 stamp", or "slab, rigid mailer, tracked label".
- The owner keeps one small rules table: weight per item, the ounces each stamp covers, the value at which tracking starts, and when a lumpy envelope needs extra postage.
- When an order breaks a rule (too heavy, too thick, too valuable), it is flagged amber before packing, not after.
- If the same buyer ordered twice that day, the screen says "ship together" and gives one combined recipe.
**Risk:** Postal rules change. If the table goes stale, the recipe is wrong on every order without anyone noticing.

**2. Name:** Learn where tracking actually pays
**The idea:** Today the cut-off between untracked and tracked postage is a guess. This direction records how each order shipped and what happened to it: arrived, reported missing, refunded or disputed. Over time it shows the real loss rate for each order-value band, and the value at which a tracked label costs less than the losses it prevents.
**Who it helps:** The owner, who sets the policy. Most orders are cheap, so a few cents saved on each order adds up.
**Why now:** Orders already come back as exported files, so the outcome data is close at hand. A few hundred orders are enough to see whether the cut-off sits too high or too low.
**Rough shape:**
- After an order ships, it carries its method (stamped or tracked) and later an outcome tag from the order export or a one-tap refund mark.
- A small chart plots loss rate against order value, with a line for the cost of a tracked label.
- The screen gives one sentence: "Raising the tracked cut-off to $X would have saved $Y over the last 90 days."
- The owner changes the cut-off with one tap, and recipe 1 uses the new value from then on.
**Risk:** Losses are rare, so for a long time the numbers stay too small to trust. The chart must say how sure it is.

**3. Name:** Photo of the packed order
**The idea:** Just before sealing, the Fulfiller takes one photo on the iPad of the card in its protection beside the open envelope. The photo is stored with the order. When a buyer reports a damaged or wrong card, the owner already has evidence of what was sent.
**Who it helps:** The owner in disputes, mostly over valuable cards and slabs. The Fulfiller, who is protected from "you sent the wrong card".
**Why now:** The capture photo already proves which card went into the box. The packed photo closes the gap between the box and the buyer.
**Rough shape:**
- The camera opens by itself only for orders above a value the owner sets. Cheap orders skip it.
- The photo goes into the order's record next to its capture photo, so the two can be compared.
- If the packed card does not match the capture photo, the order stops: "This doesn't look like the pulled card."
**Risk:** An extra step for each order on a peak night. If the value gate is set too low, the Fulfiller will start skipping it.

**Bet:** Build the pack recipe first. It touches every order every day. It removes the judgment calls a non-technical Fulfiller is worst placed to make: weight, rigidity, and tracked or not. It also records the shipping method on each order, and both other directions need that data before they can work.
