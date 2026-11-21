# p-learning

**1. Sorted Run Prediction**
**The idea:** Cards come in sorted by set and number, so the next card is usually easy to guess. The system predicts each card from the cards before it and checks the guess for free against photos the owner already confirmed. It sends a card to the paid identify step only when the run breaks, the check fails, or a random spot check picks it.
**Who it helps:** The owner. It cuts the cost of the paid step and the number of review questions.
**Why now:** Each new batch pays the identify cost again. With 3,600 confirmed photos, there is now enough reference material to check guesses for free.
**Rough shape:**
- After a capture run, a "paid reads avoided" line shows the money saved and how many cards were guessed and then confirmed.
- Breaks in a run are marked as seams, such as a missing number, a duplicate or a different printing. Only the seams go to the paid step.
- A random 1-in-N sample of guessed cards still goes to the paid step. If a guess fails there, prediction pauses for that set until the owner approves it again.
**Risk:** One confident wrong guess could repeat down a whole run, for example by getting the printing wrong for 40 cards.

**2. Overrides Become Proposed Rules**
**The idea:** The system stores each price override, damage flag and corrected identification with its reason. When the owner keeps making the same correction, the system writes it as a rule ("you price this set's holos 15% over market"; "you never list under $0.30"). The owner accepts or rejects each rule. An accepted rule then applies without asking.
**Who it helps:** The owner. Today they make the same judgment call again and again, card by card.
**Why now:** At about 3 orders a day, there are few enough corrections for the owner to read every proposed rule. That builds trust before the volume gets too high to check.
**Rough shape:**
- A "Lessons" page lists each proposed rule with the overrides behind it, how often it would have matched, and Accept and Reject buttons.
- Each accepted rule shows when it last fired and how many cards it touched. A rule the owner overrides again is flagged as drifting.
- A card the owner needs to look at shows which rules already decided it, so the owner only checks what is new.
**Risk:** A rule built from a few expensive cards could quietly misprice many cheap ones.

**3. Location Trust from Pulls**
**The idea:** Each pull by the Fulfiller tests the stored location. The card was where the system said, one slot off, in another section, or missing. The system keeps a trust score for each section, lowers it as misses come in, and suggests re-sorting only the sections that have drifted.
**Who it helps:** The Fulfiller, who spends less time searching. The owner, who re-sorts only the sections that need it.
**Why now:** On a 39-order day, one bad section costs more time than the whole rest of the pull. The record of misses only starts building once the system starts recording outcomes.
**Rough shape:**
- The Fulfiller has one tap for each pull: Found, Nearby, or Not here. There is no typing.
- The pick list adds a hint where the system has learned a pattern ("this section runs about 2 slots late").
- A heat strip shows each box's sections by trust and offers "re-capture these 2 sections" instead of a whole box.
**Risk:** The Fulfiller may tap Found by habit, which would make the data look better than the boxes really are.

**Bet:** I would build Sorted Run Prediction first. It saves money you can count from the first batch, it uses the one strong fact the business already has (cards arrive sorted), and the spot check and pause give the owner a clear way to stop it.
