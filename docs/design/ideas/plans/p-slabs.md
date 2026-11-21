# p-slabs

**1. Name:** The Vault Tripwire
**The idea:** Every card gets a value tier when it is identified and priced. When a card crosses a set value, or its price jumps between two price pulls, it leaves the bulk flow. It is no longer listed at the bulk price. It moves to a small "vault" spot, a binder or a slab case, and waits for the owner to price it by hand. Bulk stays zero-attention, and only the few risky cards ever need a person.
**Who it helps:** The owner, who today could sell a card that just spiked to $40 for its old $2 price without ever seeing it.
**Why now:** Bulk upload with no per-card review is the whole design. With 3,600 cards, a handful of spikes a month is likely, and one stale sale can wipe out weeks of margin.
**Rough shape:**
- After each price pull, a short list says "these cards crossed the line" and shows the old price, the new price and the photo.
- The owner chooses: hold the listing, reprice it, or move the card to the vault. The vault gets its own location, like any box or section.
- Before each upload, the uploader refuses to send a vault-tier card at a bulk price.
**Risk:** If the threshold is too low, the vault fills with noise and the owner stops reading the list.

**2. Name:** Grade-or-Sell Ledger
**The idea:** For raw cards above a value floor, estimate whether grading pays. The rig already has a clean, square-on photo of each card, so it can measure centering and flag visible edge or corner wear. That gives a rough guess at the likely grade, priced against recent sales of graded copies minus fees and wait time. Cards that pay go into a grading batch, and a card at the grader keeps a location ("out for grading, submission 4").
**Who it helps:** The owner, who now decides about grading by feel or not at all.
**Why now:** At this size the store has a few dozen candidates. That is too few to research by hand, but enough for one submission that justifies its fixed costs.
**Rough shape:**
- A ranked list shows each card's raw price, its likely graded price, the expected gain and a centering score from the photo.
- The owner ticks cards into a batch. The batch prints a packing list and moves those cards to an "away" location.
- When the slabs come back, each one gets its grade and cert number and returns to stock as a slab.
**Risk:** Photo grading is rough. Present it as a ranking that helps the owner choose, never as a verdict.

**3. Name:** Gold Ticket Pick
**The idea:** The Fulfiller never needs to know the game, only the colour of the ticket. A high-value line on the pick list shows up gold, with the card's photo and the extra packing it needs: toploader, team bag, rigid mailer, tracked shipping. Before packing, the Fulfiller photographs the pulled card on the iPad, and the system matches it against the photo from capture.
**Who it helps:** The Fulfiller, who gets a clear "this one is special" signal. It also helps the owner, because a wrong card or a damaged card in an expensive order causes a refund, a loss and a rating hit.
**Why now:** At median 3 orders a day, the extra step costs seconds. At a peak of 39 a day, a rushed Fulfiller is exactly when a $5 card and a $150 card get swapped.
**Rough shape:**
- Gold lines sort to the top of the pick, with the photo shown large next to the box and section.
- The iPad shows "match / not a match" against the capture photo. A mismatch blocks the order from being marked packed.
- When an order's total needs tracked shipping, the Fulfiller sees the shipping step change, in plain words.
**Risk:** Photo matching has to tell apart printings that look almost the same. A false "not a match" trains the Fulfiller to skip the check.

**Bet:** Build the Vault Tripwire first. A sale at a stale price is the most likely costly mistake in a flow built to list with no attention, and the value tier it creates is what the other two directions need.
