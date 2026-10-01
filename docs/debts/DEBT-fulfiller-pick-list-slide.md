## DEBT-fulfiller-pick-list-slide — The Fulfiller's boxes slide once when the Pick list lands

**With more than one owed card, the box list moves once when the orders read ends.** The Pick list sits above the boxes, and its height is the number of owed cards times a card's own height. That number is known only when the walk plan lands. `Fulfillment` draws a frame in the list's shape, heading plus one card, so the boxes hold still when exactly one card is owed.

- **Measured limit.** The stability spec's fixture owes one card (585 px section at 1440 and 820). The load shift there is 0.0001 at 1440 and 0.0002 at 820. A store owing more cards moves the boxes by the extra cards' height, once. Unmeasured for a real store.
- **Not fixed because the owner deferred it.** The boxes must show as soon as the cards land and must not wait on the orders read, which has no timeout. A frame cannot match a height the data has not given yet.
- **Open questions for the owner.**
  1. Pick list under the boxes: nothing above them grows, and the Fulfiller scrolls to reach the list.
  2. Accept the one slide.
  3. Pick list in its own column: a layout redesign.
- **Closes when** the owner picks one and it lands, or a store with several owed cards loads with no shift.

**Outcome at risk.** The Fulfiller reaches for a box as the list slides under the finger.
