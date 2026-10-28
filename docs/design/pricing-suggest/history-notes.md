# Price history while pricing: four options

Mockups in this folder: `history-sheet.html`, `history-inline.html`, `history-panel.html`,
`history-float.html`. Each one draws the one list from `list.html` with Gardevoir ex's history
open. All chart data are samples.
The owner picked option 4, the floating card, and asked that it open when a price field takes
focus (`docs/specs/pricing-suggest.md` section 9c). Items 5 to 8 draw that ruling.

All four draw the same chart: today's `ProductChart` (market line, the low-to-high spread each
week, the owner's sales as diamonds), with two new marks: the owner's own asking price as a
dashed step line from the day it was listed, and the suggestion as a dot. Each states the reason
and the sold range, "14 sold in 30 days, $3.10 to $4.25", once. In options 1 to 3 they show in
the history area, and the open row's own reason line steps aside. In option 4 both stay on the
row. The row's 30-day trend is read off the chart's market line, so the two agree.

1. **Keep the sheet** (`history-sheet.html`). The history door opens today's `ProductSheet` over
   `ProductHistoryView`, 420px at the right, at 1440 and 820.
   - Gain: no new surface. It is today's code, plus the two new chart marks.
   - Loss: the scrim covers the list, so the owner cannot see the row's price, tick or the
     next row while the history shows.
2. **The row opens in place** (`history-inline.html`). The history door opens a panel under its
   row with a 90-day chart, the reason, the sold range and the prices. At 820 the side column
   stacks under the chart.
   - Gain: the history sits beside the price it explains, with the rest of the list in view.
   - Loss: the rows below move down by the panel's height, and a long list becomes longer. The
     daily "copies sold" bars that today's sheet draws under the market line are not drawn.
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
     differently. At 1440 the panel does not draw the daily "copies sold" bars that today's sheet
     draws.
   - The Up and Down arrows move the selection. A new key binding must go in `SHORTCUTS` before
     it is done.
4. **A card floats over the list** (`history-float.html`). Ruled. A price field taking focus
   opens a card for its row, with no scrim, and so does the row's history door. The card is 560px
   at 1440 and 384px at 820. Its chart is 520px wide at 1440 and 344px at 820, against 380px in
   today's sheet. It shows the chart and the four prices. The reason and the sold range stay on
   the row, so each shows once. Links: `#f=1440`, `#f=820`, `#t=dark`, `#state=top`, `#state=top&fb=next`.
   - Gain: at 1440, the widest chart of the four. The focused row, with its price, tick, reason
     and sold range, stays in view, and the rest of the list stays pressable.
   - Loss: at 820 its chart is smaller than the sheet's. The daily copies-sold bars do not fit.
   - How it complies with D313 (nothing moves unless the person moved it): nothing in the list
     moves. The card lies over the list. Only the person's own focus or press opens, moves or
     closes it.

5. **Above the focused row** (default state). The card sits 8px above the focused row, over the
   rows before it. Its right edge lines up with the row's history door, and its caret points at
   the focused price field. The field shows the kit's input focus ring. The focused row and the
   next row's price field (Miraidon ex) are fully clear at 1440 and 820. "Room above" ends at the
   list's column captions, or under the sticky send bar once that bar has stuck.
   - Gain: Tab down the list and the card follows, with the next price always in view.
   - Loss: it covers the rows already passed. In this sample order those are the Needs you rows
     (Mew ex to Umbreon VMAX), which are not priced yet. At 1440 it covers their Price, From,
     door and lock columns. At 820 it covers their prices, doors and locks, and the ends of their
     meta and reason lines.
   - Heading: at 1440 the card misses the "Suggested changes" heading text. At 820 it covers the
     right end of its lede, "Ticked rows go with the next send...". The title and count stay clear.
   - Pick: this, as ruled.

6. **No room above** (`#state=top`, Iono, the list's second row). The card opens 8px below the
   row and ends 8px left of the price column, so every price field stays clear.
   - At 1440 it is the full 560px. It covers the ends of the item column (long names such as
     "Umbreon VMAX", meta and reason lines), and the Market, Lowest and Trend columns of the next
     four rows, and the "Suggested changes" lede.
   - At 820 the price column starts 428px into the list, so the card starts after the tick column
     and narrows to 372px. It covers the thumbs, names, meta and reason lines of the next four
     rows (Pikachu ex to Miraidon ex), and the "Suggested changes" heading. Ticks and prices stay
     clear.
   - Fallback drawn behind `#state=top&fb=next`: the card opens below the next row instead, right edge on
     the door. Gain: the next row stays whole, name and price. Loss: it covers the prices of the
     rows after it, which breaks "clear of the price column".
   - Pick: the ruled fallback, clear of the price column. When the owner tabs on, the card moves
     to the next row, so the name the owner needs is always the focused row's, and that stays clear.

7. **Focus.** A card opened by focus takes no focus, so focus stays in the price field. A card
   opened by the history door takes focus, and gives it back to the door when it closes. Esc
   closes it, and focus stays where it was: in the field, or back on the door. It closes when
   focus leaves the list's price fields for anything but the card. A press outside it closes it.
   A press on another price field or door moves it to that row.

8. **What Tab reaches next.** Section 9c says Tab goes on to the next price. Today's row puts the
   history door, the lock, the next row's tick and its name between two price fields, so native
   Tab leaves the price fields, and under item 7 the card closes and opens again at each price.
   Picked: b, the pricing session's pick, recorded in the spec, section 9c.
   - a. Native Tab, as today. Gain: no new key, every control stays on Tab. Loss: the card
     closes for four stops between prices.
   - b. The card stays open while focus is anywhere in a row of the list, and follows that row.
     It closes when focus leaves the list. Gain: no new key, no flicker. Loss: it changes 9c's
     close rule.
   - c. Enter in a price field moves focus to the next price field. Gain: one key, price to
     price. Loss: a new key binding, which must go in `SHORTCUTS`.
   - Pick: b.
