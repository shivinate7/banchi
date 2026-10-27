# Price history while pricing: four options

Mockups in this folder: `history-sheet.html`, `history-inline.html`, `history-panel.html`,
`history-float.html`. Each one draws the one list from `list.html` with Gardevoir ex's history
open. All chart data are samples.
The owner picks one option. Owner word: yes. Open: which option?

All four draw the same chart: today's `ProductChart` (market line, the low-to-high spread each
week, the owner's sales as diamonds), with two new marks: the owner's own asking price as a
dashed step line from the day it was listed, and the suggestion as a dot. Each states the reason
and the sold range, "14 sold in 30 days, $3.10 to $4.25", once. In options 1 to 3 they show in
the history area, and the open row's own reason line steps aside. In option 4 the reason stays on
the row. The row's 30-day trend is read off the chart's market line, so the two agree.

1. **Keep the sheet** (`history-sheet.html`). The history door opens today's `ProductSheet` over
   `ProductHistoryView`, 420px at the right, at 1440 and 820.
   - Gain: no new surface. It is today's code, plus the two new chart marks.
   - Loss: the scrim covers the list, so the owner cannot see the row's price, tick or the
     next row while the history shows.
2. **The row opens in place** (`history-inline.html`). The history door opens a panel under its
   row with a 90-day chart, the reason, the sold range and the prices. At 820 the side column
   stacks under the chart.
   - Gain: the history sits beside the price it explains, with the rest of the list in view.
   - Loss: the rows below move down by the panel's height, and a long list becomes longer.
   - How it complies with D313 (nothing moves unless the person moved it): only the press moves
     the rows below, once. The pressed row keeps its place, and the panel opens under it at its
     full height in one step. No load, read or refresh opens or closes it, and the panel holds its
     loaded size from its first paint.
3. **A side panel follows the selected row** (`history-panel.html`). At 1440 a 360px panel sits
   beside the list and shows the selected row. The list takes the 820 row shape to make room.
   At 820 the panel does not fit, so the history door opens today's sheet, as in option 1.
   - Gain: the history updates as the owner moves down the list, with no press per row.
   - Loss: at 1440 the list loses only its Trend chart. Market and Lowest, shipped stay, in the
     line under the name, and the price source sits under the price. The two widths behave
     differently.
   - The Up and Down arrows move the selection. A new key binding must go in `SHORTCUTS` before
     it is done.
4. **A card floats over the list** (`history-float.html`). The history door opens a 560px card
   under its row, with no scrim. Its right edge lines up with the door. With no room below the
   row, it opens above. It closes on Esc, on a press outside it, or on its close button. A press
   on another row's history door moves it to that row. It keeps this shape at 820.
   - Gain: the widest chart of the four, 520px against the sheet's 380px. The pressed row, its
     price, tick and reason stay in view above the card, and the rest of the list stays
     pressable.
   - Loss: it covers the rows under it while it is open, including their prices and ticks. The
     daily copies-sold bars do not fit, so only the sold sentence shows. Its reason comes from
     the row, not from the card.
   - How it complies with D313 (nothing moves unless the person moved it): nothing in the list
     moves. The card lies over the list, and only the press opens, moves or closes it.
