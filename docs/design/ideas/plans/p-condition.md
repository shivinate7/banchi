# p-condition

**1. Name:** The photo travels with the order

**The idea:** The rig photographed every card at intake. Attach that photo to the card's listing record, and later to the order line. On the pick screen the Fulfiller compares the card in hand to that photo. A dispute then gets the same photo as evidence: the card as captured, with its listed condition and the date.
**Who it helps:** The Fulfiller, who catches a wrong printing or a damaged card before it ships. The owner, who answers a "not as described" claim in one minute with no memory work.
**Why now:** At 3 orders a day, one claim is a big share of the seller rating. The commonest claims are "wrong version" and "worse condition than listed", and an intake photo answers both. The photos already exist, so this needs no new hardware and no paid step.
**Rough shape:**
- Pick list rows show the card's intake photo beside its box, section and position.
- The Fulfiller taps "matches" or "doesn't match". A mismatch holds the line and tells the owner.
- An optional pack photo of the sleeved cards on the packing slip gets stamped onto the order.
- A dispute view puts the intake photo, listed condition, pack photo and ship date on one screen, ready to copy into the marketplace reply.
**Risk:** The rig photo may show only the front at feed resolution, so back whitening and edge wear can be invisible.

**2. Name:** Flag the odd ones, default the rest

**The idea:** Don't grade every card. Run a cheap local check on each capture photo for obvious trouble: a crease line, a white edge, gross off-centering, a bent corner. A flagged card waits in a short "look at these" tray before listing. Every unflagged card lists at the default condition with zero attention.
**Who it helps:** The owner, who looks at about 30 cards instead of 3,600 and still lists in bulk.
**Why now:** Bulk listing at a default "near mint" is where wrong-condition claims start. Weighting by price means a $40 card gets a closer look and a 20-cent card never does.
**Rough shape:**
- After a capture run, a tray holds the flagged cards with the suspect region circled on the photo.
- The owner taps NM, LP, MP or "pull it". A pulled card goes to a damaged-cards section with a known location.
- A price line sets the strictness: cheap cards flag only gross damage, cards above it flag anything.
**Risk:** How often the check is right is unmeasured. Too many false flags break "zero attention per card" and teach the owner to skip the tray.

**3. Name:** Returns come back through the rig

**The idea:** A returned or claimed card has no path back into stock today. That is an assumption, because I have not seen the app. Feed the card through the rig again and show the new photo next to its intake photo. The owner then decides: restock at the same condition, downgrade, or write off. Each choice is recorded and lands the card in a known slot.
**Who it helps:** The owner, who gets honest restock condition and a damage record. The Fulfiller, who gets one "Return" action instead of a loose pile.
**Why now:** At peak days of 39 orders a few returns will happen. A card restocked blind at its old condition becomes the next dispute. The damage record also shows where damage happens: in the box, in packing, or in the mail.
**Rough shape:**
- "Return" on an order line, then the Fulfiller feeds the card, then a side-by-side compare.
- A one-tap outcome (same, downgrade, write off) writes the listing change and the new location.
- A small damage log by cause shows, for example, that sleeve-only shipping produces most bent-corner returns.
- Slabs get the same flow, keyed on the case, with a check of the case for cracks.
**Risk:** Different light between the two passes can make the photo compare noisy, so the owner judges and the system only lines the photos up.

**Bet:** Build direction 1 first. It needs no model and no paid step. It uses photos the rig already takes. It protects the seller rating, which at this volume is the most fragile thing the business has. Directions 2 and 3 both build on the photo linked to each card.
