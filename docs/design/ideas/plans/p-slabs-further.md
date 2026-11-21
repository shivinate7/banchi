# p-slabs-further

The Vault Tripwire takes a card out of bulk once its price makes it risky, before it can sell at a stale price. Bulk stays untouched. The owner sees only the few cards that crossed.

**1. Core loop (owner's view)**
1. A price pull finishes. Each card's new price is compared with the price it is listed at and with its line.
2. The owner opens one short list, "Crossed since last pull". Each row shows the photo, the name, the listed price, the new price, how many real recent sales back the new price, and where the card is.
3. A first crossing holds the listing at once. That costs nothing and can be undone. The card stays where it is.
4. If the next pull agrees, the row asks for a move: "Pull box 3, section 7, card 112 into vault slot V-14." The owner moves it and taps Moved, and the location updates.
5. The owner sets the vault card's price by hand. From then on it is listed apart from bulk.
6. Every upload is checked against the line before it is built.

When a vault card sells, the Fulfiller's pick line is gold. It says "Vault, slot V-14" in place of a box and section, shows the card's photo large, and names the packing: toploader, team bag, rigid mailer, tracked shipping. No game knowledge needed.

**2. States the screen must show**
- **Normal:** "Nothing crossed. 3,600 checked at 7:10." Show the line and the highest bulk price, so silence reads as checked, not broken.
- **Crossed up:** a held row with old and new price, how many sales back it, and Hold, Reprice in bulk or Dismiss. A confirmed row adds the move.
- **Crossed down out of the vault:** the price stayed under the exit line for two pulls. The row says "Return to box 3, section 7." By default the card goes back to its old sorted place.
- **Spike reversed next day:** "Was $40 yesterday, $3 today. Hold released, card never moved." Shown once, then gone. This is the reason a move waits for two pulls.
- **Too late:** "Sold at $2 on the 18th. Market was $38." The order and the gap are shown, plus the owner's chosen response (question 2). Each one is logged, because it is the cost being measured.
- **Upload refused:** "3 cards held back from this file. 3,597 will upload." The 3 are named. The file is built without them, so bulk never stops. A hard refusal comes only when someone edits a held card back in.

**3. Setting the line, and not crying wolf**
- Two rules. Either one fires, but each has a floor:
  - **Dollar line:** at or above $X, a card belongs in the vault tier.
  - **Jump:** at least +Y% and also at least +$Z, so $0.10 to $0.30 never fires.
- **Two sources must agree.** One odd listing can move the market price. A jump counts only when recent sales back it.
- **Gap between entry and exit:** a card enters at $20 and leaves only below $15 for two pulls. Cards near the line do not flap.
- **Cheap act first, costly act second:** holding a listing is instant. A physical move waits for a second pull.
- **Budget:** aim for 5 or fewer rows per pull. If more show up, the screen says "the line looks too low" and does not just grow longer.
- **Backtest:** before the owner sets the line, show what it would have flagged over the last month, and which of those were real.

**4. Smallest first version worth shipping**
No vault slot and no physical move yet. Ship the crossed list after each pull (hold, reprice, dismiss), the two-source jump rule, and the upload that holds back crossed cards. That closes the costly hole, a stale sale. The vault location and the gold pick line come second.

**5. The measure**
Stale-price sales per month: sales below half the market price at the time of sale, with the dollars lost. The target is zero. Pair it with the dismiss rate (rows dismissed ÷ rows shown). Above about half means the line is crying wolf.

**6. Questions only the owner can answer**
1. What loss on one card hurts enough to act on? That sets $X and $Z.
2. When a card has already sold at the stale price, do you cancel or honour the sale? Cancelling may hurt seller standing on the marketplace.
3. Where does the vault physically live (binder, slab box, a drawer), and will you move cards by hand, a few a week?
