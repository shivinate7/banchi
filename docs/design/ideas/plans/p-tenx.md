# p-tenx

**At ten times the size, what breaks first is the meaning of a card's location.** These three directions come from the brief alone. I read no files, so I did not check premises or the glossary.

**1. Addresses that survive many hands**
**The idea:** Today a location like "box 3, section 7, card 214" probably counts from the front of the section. One pull out of turn, or a card put back in the wrong place, shifts every card behind it. With 2-3 Fulfillers and 400 orders, those counts stop being true by mid-morning. Instead, each card gets a slot address that never changes, and each pull or put-back records who did it.
**Who it helps:** Fulfillers working side by side, and the owner when they ask where a card is and must trust the answer.
**Why now:** Every photo, listing and order points at today's address. Changing what an address means after 36,000 cards are captured means migrating and checking every row.
**Rough shape:**
- A Fulfiller taps "pulling". If someone else already holds that card, they see "Sam has this" and move on.
- A card that goes back in the box gets an address again. It never takes the address of a card that was pulled earlier.
- A card's page shows its last few moves in plain words: pulled by whom, put back by whom.
**Risk:** Slots that never move leave gaps, so boxes fill up and need an occasional compaction everyone agrees on.

**2. Count the neighbours while picking**
**The idea:** At 36,000 cards, no one will ever recount the whole stock, so missing cards and misfiles pile up unseen. While a Fulfiller's hand is already in a section, the app shows the photos of the two cards on each side of the target and asks "same as here?" One tap answers it. Over months, every busy section gets checked without anyone doing a separate stocktake.
**Who it helps:** The Fulfiller, who never has to do a count job. The owner, who learns about a lost card before a buyer does.
**Why now:** Each pick screen decides what a Fulfiller sees and taps. Adding a check later retrains 2-3 people. Building it in from the start costs one tap they never notice.
**Rough shape:**
- The pick screen shows the target photo between its neighbours, with a "Looks right" button and a "Something's off" button.
- "Something's off" asks one plain question, such as "missing" or "different card", and the pick carries on.
- The owner sees a short list of sections that need a look, and the cards in them stop selling until checked.
**Risk:** Too many prompts and Fulfillers tap "looks right" without looking, so the check needs a rate limit.

**3. Photo check at the packing bench**
**The idea:** At 400 orders a day, a wrong card in an envelope costs refunds and seller rating. A fixed camera over the packing bench compares each pulled card with its capture photo before the envelope is sealed. The Fulfiller only sees a green match or a "check this one".
**Who it helps:** A non-technical Fulfiller packing fast at peak, with no reading of set codes or numbers.
**Why now:** The check only works if capture photos are kept at a set quality, crop and lighting that a second camera can match. If today's photos are shrunk or thrown away, 36,000 cards must be photographed again.
**Rough shape:**
- The Fulfiller lays the card under the camera, and the order's line turns green or amber.
- Amber shows both photos side by side and asks "Same card?"
- Slabs and valuable cards always ask for a second look.
**Risk:** Sleeves, slab glare and near-identical printings (variant printings of the same card) may cause false ambers, so the check might stay advisory.

**Bet:** Build direction 1 first. Directions 2 and 3 both need an address that stays true while several people pull from the same boxes. Get that wrong now and every pick screen, count and photo link is rebuilt on top of it at 36,000 cards.
