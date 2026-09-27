## 38 — a section move's receipt names no owed cards and no next capture

**The gap.** `docs/specs/box-map.md` section 5.4 gives a section move's receipt two more lines.
One says how many of the moved cards are owed to open orders. The other says where the next
capture goes when the moved section was the last one in its box. The box map lane built the
receipt without these two lines.

**What it costs.** The move itself is correct, and undo is correct. The owner does not see that
a moved card is owed to an order until the pull list shows it. After a move of a box's last
section, the owner does not see which section the next capture joins.

**Why it is not fixed.** The box map lane deferred both lines to keep its slice to the move, the
card list and undo. The lane recorded them under "Planned, not built" in D265's spec.

**The fix, not built.** Add both lines to the receipt that `POST /boxes/<box>/sections/move`
answers, and draw them under the receipt on the Shelf.

Cites D264 (a section moves whole) and D265 (a card's order key).
