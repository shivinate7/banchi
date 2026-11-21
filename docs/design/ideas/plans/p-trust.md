# p-trust

**Two-Sided Wrong-Ship Repair**
**The idea:** A card shipped by mistake causes two inventory errors. The ordered card is still in the box but marked sold. The card that left is gone but still listed, so a later buyer can order it. Today a complaint fixes neither. Here, "undo" means repairing both records and making a fair offer to the buyer.
**Who it helps:** The Fulfiller, who can report a mistake without fear. The owner, who stops a second oversell before it happens.
**Why now:** A wrong card costs about the same at 3 orders a day or 39. At peak volume, though, the second error is the one that turns one refund into two.
**Rough shape:**
- From an order, anyone taps "buyer got the wrong card" and picks the card that went out from a strip of nearby photos in the same section.
- The system pauses that listing and puts "ordered card still at box 3, section 7, position 112" on the next pull list.
- It suggests a fix by value: refund only for cheap cards, a reship for valuable ones, with the pulled photo as evidence.
**Risk:** Picking from neighbouring photos may name the wrong card, so the repair itself needs a review.

**Every Upload Has a Reverse**
**The idea:** Before any listing file goes up, show what changed since the last upload and flag outliers, such as a price ten times its market price, or a slab priced like a bulk card. Each uploaded file is kept as a version. "Undo" builds the file that puts the previous prices back, ready to upload in one step.
**Who it helps:** The owner, who sets prices and can make a typo at 1 a.m.
**Why now:** Upload is the one action that reaches buyers in minutes. Most cards sell for little, so a few high-value mistakes carry the whole risk.
**Rough shape:**
- A pre-upload screen shows "312 changed, 4 look wrong", with the four first and their market prices next to them.
- Lowering the price of a high-value card needs its own confirm. Raising a price does not.
- A history of uploads, each with "make the reverse file" and a count of cards that sold since that upload, which a reverse cannot unsell.
**Risk:** If too many prices get flagged, the owner learns to click through the warnings.

**Measured Trust, Cheap Re-Seat**
**The idea:** The system checks its own claims. In quiet moments it asks the Fulfiller to check a few positions ("box 3, section 7, card 112: is it this?"). The answers give each box and each identify batch a measured accuracy. When a box is knocked over, or the disk is restored from an old snapshot, the box goes back through the rig. The new photos are matched against the stored ones, not identified again, so the re-seat costs nothing in paid reads.
**Who it helps:** Both people. The Fulfiller gets a reason to believe the pull list, and the owner learns which batches to doubt.
**Why now:** About 3,600 cards and 6 boxes is small enough to check by sampling and to rescan in an afternoon. At 30,000 cards neither is cheap.
**Rough shape:**
- Each box carries a plain label like "checked 40, 40 right", not a score.
- If one wrong card turns up in an identify batch, the whole batch is held: its listings are paused and its cards go to review with their photos.
- A box that was knocked over shows "re-seat", and the rescan comes back as "moved / missing / new".
**Risk:** Matching photo to photo can fail on near-identical printings, and those cards are exactly the ones re-seat must not mix up.

**Bet:** Every Upload Has a Reverse. It guards the one action that reaches buyers right away, all three parts can be built from data the system already keeps, and a price mistake is the one the owner makes alone, late at night.
