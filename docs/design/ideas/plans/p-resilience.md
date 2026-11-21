# p-resilience

Premise check: none done. The brief said not to read the repo, so I can't confirm whether any of these already exist.

**1. Name: Pocket ledger for the Fulfiller**
**The idea:** Every night, a copy of each card's location (box, section, slot, small photo, price paid) goes to the iPad and iPhone and works without the Mac. TCGplayer keeps taking orders when the Mac or the network is down. Only this store knows where each card sits, so the Fulfiller carries that knowledge with them.
**Who it helps:** The Fulfiller, on any day the Mac or the home network fails.
**Why now:** The location record is the one asset no one else holds. TCGplayer has the orders and market data has the prices. 3,600 rows plus thumbnails fit easily on a phone.
**Rough shape:**
- The iPad shows "Ledger from last night, 02:10" in plain words, and red if it is older than a day.
- The Fulfiller opens the order export or types a card name, and sees box, section, slot and the photo to match.
- They tap "pulled" on each card. When the Mac returns, the pulls replay into the store and they confirm each one.
- A pull the ledger can't explain is flagged for the owner, never guessed.
**Risk:** A stale ledger after a restock sends the Fulfiller to the wrong slot.

**2. Name: Away mode with set limits**
**The idea:** Before a trip, or when they go quiet, the owner sets "away until" and decides ahead what the Fulfiller may settle alone. Examples: refund a missing card under a set dollar amount, hold any slab order, freeze repricing and new listings. Anything outside those limits waits in a short queue, and the business keeps shipping in a safe, reduced mode.
**Who it helps:** The Fulfiller, who no longer stalls on choices only the owner can make. Buyers, who get a fast refund instead of silence.
**Why now:** Today the owner is a single point of failure for every ambiguous order. A week away at peak means late orders that can't be recovered, and seller-rating damage.
**Rough shape:**
- The owner sets away dates and three or four limits on one screen.
- The Fulfiller's home screen becomes "Today: ship 7, refund 1 (allowed), waiting for owner 2".
- Each act under a limit leaves a receipt with the rule that allowed it.
- When the owner returns, they get one "while you were away" summary to approve or reverse.
**Risk:** Limits set too loose let a pull mistake turn into many refunds.

**3. Name: Comeback check, three-way reconciliation**
**The idea:** After any outage, one check compares three versions of the stock: what TCGplayer lists, what the store records, and what is physically in the boxes. It lists every mismatch before normal work resumes. Missed outages also show up here: a TCGplayer outage on a peak day, an import that failed halfway, a stopped identify batch, a full photo disk.
**Who it helps:** The owner, who gets a clear answer to "is the business whole?"
**Why now:** Outages leave quiet damage: overselling from stale quantities, cards pulled but still listed, rows that were captured but never identified. With 3 to 39 orders a day, one oversold slab costs more than the check does.
**Rough shape:**
- The owner presses "Comeback check" and gets three short lists: oversell risk, listed but gone, here but unlisted.
- Each row has one fix with a way back: delist, relist, or send to review with its photo.
- Before a capture or identify batch starts, a check refuses to begin when photo-disk space or the last export's age would break the batch midway.
- The check ends with a "whole" stamp and the time it ran.
**Risk:** Each export has its own quirks, which can produce false mismatches and teach the owner to ignore the check.

**Bet:** Build the pocket ledger first. It covers the most likely failure, a dead Mac or a dropped network, for the person who stops first, the Fulfiller. It needs no new decisions from the owner. It also gives the comeback check its third source of truth: a record of physical pulls kept away from the Mac.
