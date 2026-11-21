# p-resilience-further

Away mode now includes both of the handover planner's ideas: the check run before leaving (as "Leave-ready") and the owner's set response for each kind of trouble (as "Calls"). The guess underneath is that the Fulfiller does refunds and cancels on TCGplayer themselves, and the app only says what to do and records it. I haven't checked that, which is why it's question 1.

**1) The loop**
- **A week before leaving:** The owner sets the away dates, and the app runs Leave-ready. It lists every card a stranger couldn't find:
  - no recorded slot
  - slot not confirmed since a re-sort
  - still waiting in the review queue
  - stored outside the six boxes (slabs, binders)
  - in a section whose divider has no label
- **Stranger test:** The app picks 10 random listed cards and the Fulfiller looks for them. Any card they can't find within a set time goes on the gap list. For each gap, the owner either fixes it or marks it "hold if it sells". The owner also looks over the calls and adjusts their cut-offs.
- **The day they leave:** The owner presses Hand over. Repricing and new listings pause, the calls switch on, and the Fulfiller's home screen changes to away mode.
- **A day away:** The Fulfiller ships the day's list. When a problem comes up, they pick its kind. The app applies the owner's call if the amount is under the cut-off and keeps a receipt; anything above it is held. Owner contact is optional: at most one short note a day, and only for a held order near its TCGplayer ship-by date.
- **Coming home:** The owner reads the "while you were away" summary and undoes what can be undone. They clear the held orders and end away mode.

**2) Screen states**
- **A. Leave-ready with gaps (owner):** "12 cards a stranger couldn't find", grouped by reason, with Fix or Hold-if-sold on each. Hand over stays allowed; open gaps are listed on the hand-over receipt.
- **B. Normal away day (Fulfiller):** A banner reads "Owner away until Fri. You can settle: missing card under $10, double sale under $10." Below it: "Ship 7", each card with box, section, slot and photo, and one "Problem" button per order.
- **C. Call made under a limit (Fulfiller):** For example, "Missing card, $2.40. Owner's call: cancel this line and refund. Do it on TCGplayer, then tap Done." Tapping Done writes a receipt that names the call and the time.
- **D. Held for the owner (Fulfiller):** For example, "Damaged slab, $85. Held. Send the buyer the 'looking into it' note. Ship-by date in 2 days." When the deadline is near, the order moves to the top of the list and goes into the daily note.
- **E. While you were away (owner):** "31 shipped, 2 settled, 1 held." Each settled act shows the call that allowed it, with Keep or Undo. Undo can put a card back in stock or relist a line. A refund can't be undone, and the screen says so.

**3) Limits and their defaults (all are my guesses; question 2)**
- **Missing card:** First search the slots on either side and the rest of the section. If it's still not found, cancel the line and refund. Cut-off: $10.
- **Double sale:** Ship the first order and cancel the second. Cut-off: $10.
- **Damaged card:** Refund under $5. Slabs are always held, whatever the price.
- **Buyer message:** Fixed replies only: shipping status, "looking into it" and "shipped today". Anything about price, condition or returns is held.
- **Spending cap:** At most $50 in refunds per away week. Once it's reached, everything is held.
- **Any order above the cut-off:** Held, whatever the trouble kind.
- **Fixed for every trip:** No repricing, no new listings and no price changes while the owner is away.

**4) Smallest first version**
- Leave-ready lists only cards with no confirmed slot, plus the stranger test.
- Calls are just the four kinds and their cut-offs on one owner screen.
- The Fulfiller's Problem button shows "settle" or "hold" and records the choice.
- The summary is that record, with no Undo; the owner fixes things by hand.
- Left out of version one: the daily note, automatic pausing (the owner simply doesn't upload), and the spending cap.

**5) One measure**
- The share of orders during away days that shipped by their ship-by date with no owner contact. Target: 95% or more. Compare it with a normal week.

**6) Owner questions**
1. Can the Fulfiller cancel and refund in TCGplayer themselves, or does the app only say what should happen? Away mode is designed on the first; if it's the second, more orders would be held.
2. Are the defaults about right: $10 per card, a $50 weekly cap, slabs always held?
3. While away, do you want at most one note a day about ship-by deadlines, or no messages at all? Away mode is designed with the daily note as optional.

The bet from the first round still stands: the pocket ledger comes first. Away mode depends on the Fulfiller finding cards alone, so the stranger test works best once that ledger exists.
