# p-automate-further

**Sort order checks identification, worked out.** Folded in: the live warning at the rig (from planner A), and paid reads only at seams plus a random spot-check, with prediction pausing per set (from planner B).

**1. The core loop, as the owner sees it**

*At the rig:*
- The owner starts a section. The system takes the run's start from the previous section's end, or the owner names the first card.
- Cards feed. Each photo gets a cheap local check: does it look like the card the run predicts?
- A tone sounds on a break, and the screen names it: "skip: expected 46, saw 47", "repeat", "face-down", "set changed".
- The owner fixes the stack and refeeds, or taps "it's right, keep going". The feed does not stop for cards that fit.

*After the batch:*
- Paid reads go only to seams (the start of a section, a set boundary, a break, any number with more than one printing) and to a random spot-check.
- Every other card is predicted from its run and marked as predicted, not read.
- Review shows only the cards a person must settle. A spot-check that fails pauses prediction for that set: every predicted card in it goes to paid read, and the owner sees why.

**2. The states a screen must show**
- **Normal:** each section is one strip, for example "set X, 41 to 88, 47 cards, 3 seams read, 1 spot-check passed". There is no list of cards.
- **Empty:** no anchor yet. "Feed a card, or name the first card of this section." Nothing is predicted until an anchor is read.
- **Hard case, playset:** four copies of number 12 are expected, not flagged as repeats. The strip shows "12 ×4". A fifth copy sounds the tone.
- **Hard case, printings:** a reverse holo next to a normal print of the same number. Sequence gives the number but never the printing, so both get a paid read. The strip shows "number by run, printing by read".
- **Hard case, mixed section:** two sets in one section. Each set boundary is a seam, with a new run and a new anchor. The strip splits in two.
- **Failure:** a wrong card is found later, at a pick or in a buyer report. That card is corrected. Its run is marked suspect back to the last read anchor, those cards are queued for paid read, the set's prediction pauses, and the owner sees the count and the cost.

**3. What the system must know, and what is new**

*Already known (from the brief):* box, section and position per card; paid identify results.

*Must already exist or be added:*
- Catalog per set: its numbers, which numbers have several printings, and a reference image per card.

*New to record:*
- How each card is known: read, predicted, or confirmed by a person.
- For each predicted card, the anchor it hangs from.
- Each rig warning and what the owner did about it.
- Spot-check results per set, and whether prediction is paused for that set.

**4. The smallest first version worth shipping**
- After the batch only. No tone, and no paid reads skipped: every card is still read, as today.
- Sequence acts as a second vote. A low-confidence read that fits its run is accepted. A read that breaks the run goes to review.
- This removes most review work with no new guessing. It also measures how often run and read agree, per set. That agreement rate is the evidence needed before the version that skips paid reads.
- The tone comes second, and paid reads only at seams come third, set by set, once agreement earns it.

**5. One measure**
- Cards a person looked at per 100 captured. It counts as a win only while wrong cards found later stay at zero.

**6. Questions only the owner can answer**
1. Does a card predicted from its run, with a passing spot-check, count as identified? Or must every card get a paid read or a person, under the rule never to guess an identification?
2. Within one number, is the order of your sorted stock fixed (normal print before reverse holo, copies of a playset together)? Is it fixed enough to rely on?
3. What does one wrong card cost you: refund, feedback, the Fulfiller's time? That answer sets the spot-check rate and the price above which every card is always read.

**Bet, unchanged:** build the version that only adds a second vote first. It costs nothing in accuracy, cuts review now, and produces the agreement data that would justify the tone and skipping paid reads.
