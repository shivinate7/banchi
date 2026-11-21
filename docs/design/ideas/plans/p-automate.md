# p-automate

**Name:** The sort order checks identification

**The idea:** Cards arrive sorted by set and card number, so the order they feed past the camera already says a lot about what each card is. Treat that order as a second witness beside the paid identify step. A card whose reading fits the run passes with no human. A card that breaks the run goes to a person. Most of the review queue disappears, and so does part of the identify bill, because a card that fits the run between two confirmed neighbours may need only a cheaper check.
**Who it helps:** The owner, who now reviews only real breaks in the run, not every low-confidence reading.
**Why now:** About 3,600 cards today, 1,300 an hour through the rig. Review grows with every batch, and the pre-sorted feed is a free signal that is going unused.
**Rough shape:**
- After a batch, a strip shows the run per section (set X, numbers 41 to 88) and marks only the gaps and out-of-order cards.
- A break shows its photo beside its two neighbours. The owner picks the card in one tap or marks it as misfiled.
- A card that fits the run never appears on any screen.
**Risk:** Sequence cannot tell printings apart: a normal print and a reverse holo share a number. Printing stays with the paid read or a person, and the order never names a card on its own.

**Name:** Owner sets rules, not prices

**The idea:** The pricing screen stops existing as a place where prices are set card by card. The owner writes a few standing rules (follow market price, never below a floor, sit within a band of recent sales). Listings reprice on a schedule and upload themselves. The only screen left is an exceptions list: a slab, a card above a value line, or a price move the rules will not accept.
**Who it helps:** The owner, who gets back the recurring pricing pass across every card.
**Why now:** Most cards sell for under a few dollars. A person adds no value pricing a $0.40 card. The few valuable cards are exactly where the owner's attention pays.
**Rough shape:**
- One page of rules in plain words, with a preview: "this would change 212 prices; 4 need you".
- A weekly digest: what moved, what sold under the old price, which exceptions are waiting.
- Slabs and high-value cards always ask. Everything else just happens.
**Risk:** A bad rule or a thin, spiky market reprices hundreds of cards at once. It needs a ceiling on how far prices may move per run, and a one-step undo.

**Name:** Paper is the Fulfiller's interface

**The idea:** The orders and shipping screens disappear for the Fulfiller. When order files arrive, the system prints one pick sheet in walk order (box, section, position) with the packing slips and labels already grouped by order. The Fulfiller never opens a browser. They pull, pack, ship, and tick the sheet. Exceptions (not found, damaged) are a mark on paper that the owner enters later, or a single tap.
**Who it helps:** The Fulfiller, who needs no training on software, and the owner, who stops supporting it.
**Why now:** At 3 orders on a median day, a screen costs more attention than the work itself. A peak of 39 orders is when a sheet in walk order saves the most steps.
**Rough shape:**
- The order file lands, and a printer produces the sheet: cards in shelf order, with a small photo of each card so it can be matched by eye.
- Each line carries its order letter, so the stack of pulled cards sorts straight into envelopes.
- "Missing" is a checkbox. A missing card goes to the owner's queue, not the Fulfiller's.
**Risk:** The order file still has to be fetched from the marketplace. If that step stays manual, the owner has only moved the screen, not removed it.

**What still needs a person:** printing differences the photo cannot settle, slab and high-value prices, and a card that is physically missing.

**Bet:** The sort order check. It uses a signal the business already produces for free, it shrinks both the review queue and the identify spend on every batch from now on, and getting identification right is what makes the pricing rules and the pick sheet trustworthy.
