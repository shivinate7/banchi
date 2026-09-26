## 40 — a divider save can move a divider past departed records

**The defect.** The divider editor speaks card numbers, and the store keeps order keys. The cards
in front of a divider can have left the box. Then an edited start maps to the first card on
hand, and the save puts the divider after the departed records. An unchanged start keeps the
stored divider, so only an edited start does this.

**Found by** the box map lane's R5 review, rated LOW. It is older than the lane.

**What it costs.** A departed record can land in the section before its divider, not after it.
The cards on hand keep their labels. Only where a departed record sits in the history changes.

**Why it is not fixed.** The box map lane recorded it and did not fix it. It kept its slice to
the move, the card list and undo.

**The fix, not built.** Map an edited start to the key of the first record at that place,
departed or not. Then the divider keeps the departed records on its far side.

Cites D58 (a card's number counts the cards in the box), D134 (a departed record is buried) and
D265 (a card's order key).
