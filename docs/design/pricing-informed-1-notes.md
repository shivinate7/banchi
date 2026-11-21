# Pricing, one send line: notes on the mockup

Designer kind: informed. Mockup: `pricing-informed-1.html` in this folder. It opens from disk
with no server. Screen: `#/pricing`, `Pricing.Pricing` in `app/src/Pricing.tsx`. Specs:
`docs/specs/pricing-suggest.md` (signed off) and `docs/specs/stale-listings.md`. Debts: DEBT89
(the send bar draws, then leaves), DEBT90 (a send notice joins the bar late), DEBT91 (the send
press widens). Every figure, card and name on the page is made up. The CSS is
`app/src/tokens.css` and `app/src/fonts.css`, inlined, and the kit rules the page uses, copied
by name from `app/src/kit.css`. The list rows and the floating history card follow the signed-off
`pricing-suggest/list.html` and `pricing-suggest/history-float.html`.

Deep links: `#s=loaded`, `loading`, `failed`, `empty`, `nomatch`, `card`, `held`, `review`,
`sending`, `sent`, `leftout`, `done`. Add `&w=1440` or `&w=820` (default: both frames), and
`&t=light`, `dark`, `abyssal-bloom` or `carnival-midway` (default: `prefers-color-scheme`). Add
`&o=<key>` to try an option on the frames, `&hide=<key>` to cull one, `&tags=off` to hide the
dashed Today and New tags. Option keys: `fold-rule`, `review-sheet`, `unit-listings`,
`movers-line`, `reason-sentence`. Each option has an element id `opt-<key>` in the options panel.

## Measured, with the mockup and the live demo (headless Chromium)

| | Today (demo) | This mockup |
|---|---|---|
| Lines before row 1 | 9 status lines | 1 send line, a rule chip, a status chip |
| Row 1, from the page top | 753px at 1440, 772px at 820 | 308px at both |
| Send line height, all 12 states | changes (DEBT89, DEBT90) | 80px at 1440 and 820, every state |
| Send press width, all 12 states | grows at landing (DEBT91) | 304px at 1440, 252px at 820, every state |
| Door positions, all 12 states | shift at landing (DEBT91) | x 1304 and 1348 at 1440, 756 at 820, every state |
| Row heights | about 110px at 820 (122,000px for 1,110 rows) | needs and suggested 80px at 1440, 98px at 820; at the rule 49px and 66px |
| Page, every row drawn | 97,542px at 1440, 121,954px at 820 | about 56,000px at 1440, about 75,000px at 820 (sum of the measured rows) |
| Page, option `fold-rule` | | about 8,200px at 1440, about 10,000px at 820 |

## Choices

1. **One send line, 80px, every state.** The slot on the left holds the ledger, the pending
   bars, the failed line, the empty line, the sending line, the receipt or the left-out notice.
   Nothing is added under it, so the list never moves (D313, nothing moves unless the person
   moved it). A detail opens as a float over the list (the moves, the receipt names), as
   `send-card-notes.md` item 2 already does. Gain: closes DEBT89 and DEBT90 by shape; a test
   compares one height. Loss: a standing receipt shows one line, and its names need a press.
   Pick: as drawn.
2. **The press keeps one box from first paint.** Two lines inside a fixed width: "Send 110
   copies to TCGplayer" and "92 live copies move to new prices". Pending, it reads "Send to
   TCGplayer" and "Counting what goes…" in the same box. Gain: closes DEBT91. The second line
   keeps the owner's ruling that the button names every live copy that moves
   (`send_routes._named_moves`, round 7, R6-3; `SendCard.MovesPhrase`). Loss: the label is
   smaller than today's one-line press. Pick: as drawn.
3. **One unit: copies.** Today one count has three units: "64 copies ready" is
   `figures.units`, which sums rows by kind (11 + 15 + 31 + 7, `Pricing.tsx`, the `units:` line
   of the figures memo); the press counts `progress.outRows` (SKUs) and the live moves
   (`SendCard.pressCarries`, `MovesPhrase`); Home counts `sendCounts(...).ready`
   (`Home.tsx`, `readyCopies`; `standing.pricingTileNote`). Here every count is copies: the
   ledger, the press, the "What goes" panel. Home's tile must say the same number. This follows
   `pricing-suggest/list-notes.md` item 13 ("Send N copies"). Gain: one number in three places.
   Loss: none seen. Pick: copies. Option `unit-listings` draws listings instead.
4. **The five tallies become a four-cell ledger.** New, rise, fall, typed, each a count with
   its money under it, today's words (`Pricing.tsx`, `.pricing-figures-parts`). "Kept off" leaves
   the ledger: the toolbar's "Show kept off 31" already carries the count, and two showings break
   ux-label-once. At 820 the money hides and "What goes" opens it. Pick: as drawn.
5. **"What goes" is a float, not a step.** It lists each kind with copies on cards and money,
   the live copies that move with their old and new price, and the kept-off count. The press
   still sends in one press (D273, one press sends listings live; D277 Q7). Pick: as drawn.
6. **The status chip replaces six lines.** "Prices have not been refreshed", the two "no read
   has run" lines, "12 could not be checked", "Excluded: 14 in 2 readings" and the movers line
   fold into one chip: "2 to check", which opens a float with one press per item. With nothing to
   check it reads "All is well." (ux-all-is-well). Before the list loads it reads "Unknown"
   (ux-unknown-is-not-empty). Gain: the first screen is the list. Loss: a stale read is one press
   away, not in sight; the chip's dot is amber. Pick: as drawn.
7. **The movers line leaves.** Spec section 9a picks cutting it; the owner has not ruled. The
   chip draws it only under option `movers-line`. Owner grant: yes.
8. **The rule chip.** "New cards list 5.5% over market, $0.15 floor. Value line $25.00." with
   Change, beside the title. Today's words, today's sheet (`Pricing.RuleSheet`), one line
   instead of two (D277 Q5: one line above the list, with Change). At 820: "Rule +5.5%, floor
   $0.15, value line $25.00". Pick: as drawn.
9. **Reasons as chips.** Each fact is one chip; a needs-you fact is amber. A row is two lines at
   1440, never a paragraph. The full sentence lives in the history card. Gain: rows drop from
   about 110px to 80px. Loss: the reason no longer reads as a sentence on the row. Pick: chips.
   Option `reason-sentence` draws one cut line instead.
10. **Rows at the rule are one line.** Name, set and copies inline; no reason line. 49px at 1440.
    Every row stays on the page (spec section 1, "Every row, made clearer"). Pick: as drawn.
11. **Fold "Going at the rule".** One line, "983 rows at the rule, listing for $412.30", and Show
    them. The page drops to about 8,200px. Departs from: spec section 1 and section 3 ("still on
    screen"). Owner grant: yes. Pick: no, unless the owner reopens section 1.
12. **Review sheet before Send.** The press opens a sheet; a second press sends. Departs from:
    D273, one press sends. Owner grant: yes. Pick: no.
13. **The history card is today's pick.** It opens on a price field's focus, sits above the row
    and takes no focus (spec section 9c). It carries the full reason sentence. Pick: as drawn.
14. **Keep off TCGplayer.** The lock press dims the row in place, shows "Kept off", turns into
    "Put back in the send", and the ledger and kept-off count change at once. The row keeps its
    slot until the next sort (ux-order-holds-still). Words: list-notes item 11. Pick: as drawn.
15. **Receipt rows.** After a send, a row that went shows a green check in the From column, not
    the word "Sent" (ux-label-once). A left-out row comes back ticked at its new price with an
    amber chip, "Left out: TCGplayer moved to $4.30" (send-card notes item 8). The press then
    offers those copies alone. Pick: as drawn.
16. **Loading keeps the shape.** The toolbar, the caption and a group head draw while the list
    loads, so row 1 lands 5px from its pending place or less. Pick: as drawn.
17. **Empty and done keep today's words.** Zero runs: "Nothing to price" with today's body and
    two presses, Refresh and Go to Review (`Pricing.tsx`, the `EmptyState` with `roster.length
    === 0`). Done: each group says it is clear in its own line; the rule rows stay. Departs
    from: today's done page, "Everything is sent", which hides the list. Not blocking.
18. **No Stop on Send.** ux-long-run-stops asks for one. A Stop mid-publish needs a server
    cancel that rolls back at TCGplayer (D273: a failed push rolls back). The mockup draws none.
    Owner grant: yes, if a Stop is wanted.

## Label check

`python3 ~/.claude/lint/label_once.py` over each state's rendered frame. The repeats left are row
data: set names, the source pill per row (spec section 2, every row says where its price came
from), reason chips, and "Now" before each live price. At 820, "Market" and "Lowest" label each
row, as today (`docs/DESIGN.md`, the `bn-page 899` refinement). In the "What goes" float the
kind names repeat the ledger's, on purpose: the float is the ledger's detail.

## Changes outside the design folder (for a builder)

- `SendCard` press: fixed width and two lines (item 2). `Pricing.tsx` pending bar: the same box.
- `Pricing.tsx` figures and `standing.pricingTileNote`: one count in copies (item 3).
- The status chip and its float: a new kit component, or a `Notice` variant (item 6).
