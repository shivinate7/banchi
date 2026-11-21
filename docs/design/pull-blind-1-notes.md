# pull-blind-1: filling the day's card orders

Designer kind: blind. Mockup: `pull-blind-1.html` (opens from disk, no network).

I did not read the current screen, its code, the spec or the repo tokens. So every part on the
page carries a dashed "New:" tag and none carries "Today:". No item has a "Departs from:" line,
because I cannot know the current behaviour. A reviewer who knows today's screen should mark which
items depart from it.

Deep links take `c` (walk, map, stack), `s` (start, mid, check, spare, end, done, allwell,
loading, failed, empty), `d` (quiet, busy, peak), `w` (1440, 820), `t` (light, dark), `h` (hidden
concepts) and `tags=off`. Example: `#c=map&s=mid&d=peak&w=820&t=dark`.

Each concept has a Hide button in the bar above the frame. The focus element of each concept is
its root: `#concept-walk`, `#concept-map`, `#concept-stack`.

## Concepts

1. **Shelf walk.** The helper first lays out numbered envelopes. Then the screen shows one card at a
   time, in the order the boxes sit (Box 1 front to back, then Box 2). Each card shows where to reach,
   the photo, and which envelope it goes in. A side list shows what comes after.
   Gain: one thing to do at a time, and the least walking. It needs no explaining beyond the first
   screen. Loss: the helper cannot see a whole buyer's order at once. The envelopes must be laid out
   before the first card. Pick: **yes, my first choice** for a helper who is not technical.

2. **Shelf map (the bold one).** The screen is a drawing of the shelf, seen from above: six long
   boxes, split into their tabs, front on the left. Each card to take is a dot at its real depth in
   the box, and the dot's number is its envelope. A square holds a few cards that sit close together.
   There is no list. An envelope tray at the bottom lights one buyer's dots. Press a dot to get the
   card sheet. Gain: the helper sees the whole job and where it is, so a glance answers "how much is
   left in Box 4?". Loss: it needs one sentence of help (dots, numbers, squares). On a peak day, the
   squares hide which envelopes they hold until pressed. Pick: keep it as a contrast. It may suit the
   owner more than the helper.

3. **Envelope stack.** One buyer at a time. The open envelope lists its cards in shelf order; the
   first one is open with its photo and its place. When every card is in or short, "Next envelope"
   opens the next. The pile on the left (a strip at 820) opens any envelope out of order.
   Gain: the envelope in the helper's hand is the buyer on the screen, so a card cannot go to the
   wrong buyer. It fits the median day (3 orders, 1 card each) best. Loss: on a busy day the helper
   walks the shelf once per buyer. Pick: second choice. It could be the quiet-day mode of Shelf walk.

## Shared choices (all three concepts)

4. **One copy per step.** Each step is one copy at one place. A card owed twice is two steps, and
   each step says "Otto needs 2 of this card. The other is at Box 5, tab C, card 21."
   Gain: one press equals one card in hand, so counts never drift. Loss: two copies side by side take
   two presses. Pick: one copy per step.

5. **Which copies to take.** When more copies are on hand than owed, the screen takes the ones that
   come first in shelf order and keeps the rest as spares. Gain: shortest walk. Loss: it ignores
   condition; a lightly played copy may be picked before a near-mint one. Pick: shelf order.
   Owner grant: yes.

6. **A spare replaces a copy that is not there.** "Can't find it" on a copy with a spare puts the
   spare on the list at once, and the answer says where it is. With no spare, the card goes on the
   missing list. Gain: no decision for the helper. Loss: an extra walk the helper did not choose.
   Pick: automatic, with Undo. Owner grant: yes.

7. **Two ways a copy fails.** "Can't find it" and "Not the card in the photo" are separate buttons.
   Gain: the owner learns whether a card is gone or misfiled. Loss: one more choice per card.
   Pick: keep both. Cull to one if the owner does not need the difference.

8. **Sold is marked at "Put in envelope".** One press puts the card in, marks it sold and shows a
   receipt with Undo at the button. Gain: the check and the sale are one act, so nothing is left
   half done. Loss: a slip sells a card until Undo. Pick: one press with Undo. Owner grant: yes.

9. **The missing list goes to the owner in one send.** Cards with no known spot are on the list from
   the first screen. Cards that fail join it. "Send to owner" sends the list, and the helper may
   send early. Gain: the owner hears once, with each card's reason. Loss: I do not know how the owner
   wants to hear (on this screen, a message, a printout). Pick: one list, one send, with Undo.
   Owner grant: yes.

10. **Envelopes carry a number and a name.** The helper writes both. The same number shows on each
    card, dot and tile, in a colour. Colours repeat after eight, so the number is the key and the
    colour only helps. Gain: a number is faster to match than a name. Loss: if envelopes come
    pre-labelled, the writing step is waste. Pick: number and name. Owner grant: yes.

11. **The place reads Box, Tab, Card on a highlighter band, with a front-to-back bar.** "37 of 58
    in this tab, in the back half." Gain: the helper goes near the card without counting from the
    front. Loss: it assumes the position number counts from the front of the tab. Pick: band and bar.
    Owner grant: yes, to confirm how positions are counted.

12. **Walk order wraps.** After a spare joins behind the helper, the cards ahead come first, and the
    one behind comes last with "Back to Box 1 for this one." Gain: no back-and-forth. Loss: the list
    order is not plain box order at the end. Pick: wrap.

13. **The photo check.** The photo is large beside the place. Pressing it opens a larger view that
    carries the same three buttons, so the helper can act without closing it. Gain: the check is
    part of the step, not a separate screen. Loss: none seen. Pick: inline photo plus zoom.

14. **Touch at 820.** The main button is 72 px tall, other controls are at least 48 px, and the
    buttons sit in the lower half. Gain: a hand that holds a card can still press. Pick: as drawn.

15. **States.** Loading keeps its size. "Couldn't load the orders" has Try again and the server text
    behind "What the server said". No orders is one sentence and "Check again". When nothing is short
    at the end, the summary says only "All is well." (`s=allwell`, quiet day).

16. **Any card can be undone, not only the last.** The receipt at the button undoes the last press.
    A finished card (a row in Envelope stack, a dot's sheet in Shelf map) has its own Undo.
    Gain: a mistake found three cards later is still fixable. Pick: as drawn.

## Drawing choices

17. **Sizes.** The brief gives widths only. I drew 1440 x 900 and 820 x 1180; both heights are my
    choice. The frame scales down to fit a narrow window.

18. **Look.** System font throughout. Colours are my own, named by role: a highlighter yellow for
    the place to reach, green for "in", a dashed red-orange for "missing". Card art is drawn, not a
    real card. Every name, card and count is made up.

19. **Day sizes.** Quiet (3 orders), Busy (7) and Peak (39 orders, one of 43 cards) switch in the
    bar, so each concept can be judged at the peak.
