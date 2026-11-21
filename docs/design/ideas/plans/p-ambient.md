# p-ambient

**Bet: Tombstone slips.** It is the cheapest of the three, about $40 of hardware with no wiring in the boxes, and it fixes a problem the other two would inherit. Here are three directions where the room tells people what to do without a screen.

**1. Name: Dividers light up to pick**
**The idea:** Put a cheap addressable LED strip along each long box (an ESP32 board running WLED, about $15 a box) so that one LED sits behind each divider. When an order arrives, the sections that hold its cards glow, each order in its own colour. A section goes dark once its pull is confirmed. One lamp by the door shows whether any orders are waiting, so nobody has to open an app to check.
**Who it helps:** The Fulfiller, who reads the room instead of a list, and the owner, who can see from across the room whether the day's orders have been pulled.
**Why now:** On a peak day of 39 orders, pulls land in 9-22 sections across 6 boxes. Colour groups those pulls by order better than any list can.
**Rough shape:**
- The Fulfiller walks in, sees amber in three sections of box 2 and green in box 5, and pulls from them.
- They press a single button on the box (or the light times out) to say a section is done.
- Slabs and valuable cards blink, which means "handle with care, check twice."
**Risk:** A strip that gets bumped out of line lights the wrong divider, and people trust a light more than a list.

**2. Name: Tombstone slips hold the slot**
**The idea:** A $40 thermal receipt printer prints one slip per sold card. Each slip carries a dithered thumbnail, the box, section and position, the order number, and the names of the cards on either side. The Fulfiller swaps the card for its slip: the card goes into the mailer and the slip stays in the gap. The slot then reads "sold, #1234" rather than being silently empty. I assume positions are recorded as a count from the front of the section. If so, they stay true after a pull.
**Who it helps:** The Fulfiller, who gets paper they can hold and a clear way to check their work. The owner gets inventory that does not drift between captures.
**Why now:** At 3-11 orders a day, about 3,600 recorded positions drift a little with every pull. The capture rig's main promise, "know where every card is," wears out quietly.
**Rough shape:**
- The slips come out of the printer in walk order, as one strip per run.
- The Fulfiller tears off a slip, finds the slot from the neighbour names, swaps the card for the slip, and does the same for the next.
- At the next re-capture or restock, the rig sees a tombstone and knows the gap is meant to be there. A tombstone with no order behind it is flagged as a mystery.
**Risk:** Tombstones pile up and thicken the box unless a re-capture or restock clears them out.

**3. Name: E-ink tabs on every divider**
**The idea:** Surplus electronic shelf labels (around $3-6 each, flashed with the open-source OpenEPaperLink firmware) clip onto each divider. They show the section's card range, the number of cards in it, "3 to pull" or "full", and the section's total value. The battery lasts years, and the tabs update over the air from the Mac.
**Who it helps:** Both people, because the tabs turn the boxes into the index. The owner sees where the value sits and which sections are filling up.
**Why now:** About 100 dividers is a small enough count to tag cheaply. Sections of 545-732 cards a box are too big to search by memory.
**Rough shape:**
- The Fulfiller scans the tab tops for a "pull" badge and never opens a screen.
- After a capture batch, the tabs refresh with new ranges, so a restock goes into the right slot.
- A tab shows "re-capture me" when its count no longer matches the store.
**Risk:** A tab only updates every few minutes and runs a hobby firmware stack, so it can show stale numbers or drop off the network without anyone noticing.

**Why the bet:** Directions 1 and 3 point at positions, and positions only stay true if a pull leaves a marker. A slip also tells the Fulfiller where to go and checks their pull. Lights or tabs can come afterwards, once positions hold.

I wrote this from your brief alone, as asked, and read no file. Whether positions are stored as a count from the front is unknown, and the case for tombstones depends on it.
