## D-position-ruler-ticks — The card ruler ticks every 5th card

**The owner picked design B.** The card ruler under the section strip (`PositionBar`) draws a thin
tick at every 5th card. Every 10th tick is darker, taller and carries its number. A tick stands at
the card's own cell center, where the pin stands. The last card is never ticked, because the end
label says it. A number within 1 card of the end is dropped for the same reason. Past 100 cards
the pitch is 10 and the numbers fall every 50 (`rulerTicksOf`).

**One set of lines.** The ruler's old comb (a 1-2-5 ladder of teeth) is deleted, and the ticks
replace it. The section strip above draws section boundaries as chips, a different instrument,
and is unchanged. The pin, the filled cell and the end labels are unchanged. The ruler's height
is unchanged (D155, D118): the numbers sit in the top band, the end labels at mid-height.

**A chip names the card.** A small accent chip beside the pin shows the card's number. It uses
`--bn-accent` and `--bn-on-accent`, so both themes read. It sits at mid-height, under the tick
numbers, and flips to the pin's left past the ruler's middle so it never meets an end.

**No caption under the section strip.** The gray `Position N of M` line is gone. It was the
section number and read as a card count beside `Card 14 of 48`. The header says `Section N`, and
the chips say the rest. `back` and `front` are written once, under the card ruler, because both
strips run the same way. The strip has no pair of its own. The Fulfiller's `Position N of M` is a card
count and keeps its word.

**The copies header drops the set code.** The card header above the panel already draws it. The SKU,
the condition and the counts (`sent`, `waiting to go live`, headroom) are said nowhere else on the
panel, so they stay. The number stays as well. A group whose copies spell it three ways has none
in the card header, and this line is where the group's agreed number lands.

**Amends** D155 (the ruler's graduations) and D260 (card numbers count within a section).
