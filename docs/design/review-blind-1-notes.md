# review-blind-1: notes

Designer kind: blind. Screen: answering doubtful cards, and the paid read. Mockup:
`review-blind-1.html`. Every figure, card, set and price in it is made up.

Two concepts, each with its own structure, its own way to move and its own first screen:

- **Bench**: one card at a time. The photo is on the left, its printings are on the right. Tabs:
  To answer, Answered, Paid reads. First screen: the next open card.
- **Sorting table** (the bold one): the unit of work is a pile, not a card. Photos whose
  candidate printings are the same make one pile. The printings stand still as bins across the top;
  only the photo changes. Boxes and their paid reads sit in the left rail. First screen: the
  largest pile, with its bins.

Deep links: add the hash to the page path. `c` = `bench` or `table`. `s` = state (the page's State
menu lists each one). `t=dark` or `t=light`. `w=820` for the tablet frame. `hide=bench` or
`hide=table` hides a concept. `off=<concept>.<part>` hides a part. `new=1` shows the "New:" outlines.
Examples: `#c=table&s=eight&w=820&t=dark`, `#c=bench&s=read-cost`.

## Choices

1. **Bench: one card, printings beside it.** Gain: the plainest path from photo to answer;
   any card shape (2 to 8 printings) works the same way. Loss: the printings change with every
   card, so the eye relearns the reference each time, for hours. Pick: keep as the safe concept.
   Owner grant: yes (a structure for the screen; a blind designer cannot see which spec it
   changes). Hide: the Hide button beside "Bench".
2. **Sorting table: piles of photos that share the same printings, dropped into bins that stay
   put.** Gain: the reference images stay still while only the photo changes, so each answer is one
   comparison; a pile of 14 look-alikes goes fast. Each photo still gets its own drop, so nothing is
   guessed in bulk. Loss: a pile of one is the Bench with more chrome; grouping needs the exact same
   set of candidates; a wrong drop needs the bin tray or Undo. Pick: the bold concept; I would test
   it against the Bench on one real sitting. Owner grant: yes. Hide: the Hide button beside
   "Sorting table".
3. **Differences only.** Each printing shows only the marks that differ among the candidates
   (stamp, finish, border, art, language); set and number are already in its title. A mark that
   sets this printing apart is strong; a mark most share is quiet, and at 8 printings it is hidden.
   Gain: the deciding mark is the loudest thing on the row. Loss: the full record of a printing is
   not on screen. Pick: on. Hide: "Parts to cull", Differences only (both concepts).
4. **Look there.** Each of the about 19 doubt reasons names a spot on the card. A press (or Z)
   zooms the photo to that spot. Gain: the owner goes straight to the mark that decides it. Loss:
   needs a spot per reason kind; a reason with no spot ("photo is blurred") gets no button. Pick:
   on. Hide: "Parts to cull", Look there.
5. **One key sends the answer** (Bench and Sorting table). 1 to 8 picks a printing, 0 is none of
   these, H is can't tell yet, U is undo. The pressed printing flashes "Chosen" and the last answer
   shows under the buttons with Undo. Gain: one key per card, for hours. Loss: a slip sends a wrong
   answer until undone. Pick: one key. The other option, **Confirm with Enter** (Bench), arms a
   printing with its number and sends it with Enter. Hide: "Parts to cull", Confirm with Enter
   (off by default).
6. **Can't tell yet holds the card, never drops it.** A held card stays in the list, striped in the
   sitting strip, and comes back after the open ones (Bench); a held photo goes to the bottom of its
   pile, and a finished pile says how many are held (Sorting table). "Every card answered" shows
   only when no card is held. Gain: nothing is guessed and nothing is lost. Loss: none seen. Pick:
   keep in both.
7. **Sitting strip** (Bench). One cell per card in the sitting: open, answered, held, or new from a
   fresh read. A press on a cell opens that card. Gain: the owner sees where they are in a long
   sitting. Loss: past 100 cells the cells get thin. Pick: on. Hide: "Parts to cull", Sitting
   strip.
8. **Paid read: the cost shows before the spend button exists.** Pick a box, the page works out
   the cost, then the button reads "Spend up to $7.34". While it runs: money spent so far, photos
   read, and Stop. After: a receipt with photos read, cost, named and doubtful. A stopped or failed
   read says what was charged and what was not, and offers to read the rest at its price. Gain: the
   owner never spends without seeing the figure and can stop at any time. Loss: one more step before
   the spend. Pick: keep in both. Bench puts it in a side panel from the Paid reads tab; Sorting
   table runs it inside the box's own card in the rail, so the receipt stays with its box.
9. **Where the record of paid reads lives.** Bench: a Paid reads tab with a table of every read
   (photos, cost, named, doubtful) and a total row. Sorting table: each box carries its receipt, and
   older boxes fold into one line with their total. Gain (Bench): one place to compare reads. Gain
   (table): cost sits next to the photos it bought. Loss: each lacks the other's view. Pick: the
   concept's own; either moves to the other.
10. **A way back.** Bench: an Answered tab lists this sitting's answers with Change, and the 46
    earlier sittings with card counts and time. Sorting table: each bin keeps a tray of the photos
    dropped in it; a press on one takes it back. Gain: any answer can be changed. Loss: the tray
    gets crowded past 8 thumbnails (it shows the last 8 and the count). Pick: keep. Hide (table):
    "Parts to cull", Bin trays.
11. **Fanned pile** (Sorting table). The next two photos show behind the top one. Gain: the pile
    reads as a pile. Loss: some noise behind the photo. Pick: on. Hide: "Parts to cull", Fanned
    pile.
12. **New doubtful cards join the end.** After a read, its doubtful cards go after the ones already
    open (Bench: dashed cells in the strip; Sorting table: new piles at the end of the rail, marked
    with their box). Nothing already in the list moves.
13. **One status line.** It names only what is not normal: a read running, a read that stopped, a
    box that has not reported back. Otherwise it says "All is well."
14. **Loading, failed, unknown, empty and filter-emptied are each their own state.** Failed says
    answers are saved, offers Try again, and keeps the server's words in a closed "What the server
    said". Unknown says which box has not reported back and offers Check again. Empty is one
    sentence and one control (start a paid read). A filter that empties the list keeps the filter and
    offers "Show every reason".
15. **Money has its own colour role.** Every cost and every spend control uses one ochre role, in
    both themes, so spend is never mistaken for a plain action.
16. **A printing's name is unique.** Set and number, then each mark that is not the plain default
    ("First Tide 012/098, foil"). Two printings never share a label in a receipt or the Answered
    list.
17. **At 820 with touch.** Bench: the photo on top, the printings as a two-column grid of large
    targets below. Sorting table: the rail folds behind "Piles and boxes"; the photo comes first,
    the bins below as a compact grid. Key hints are hidden at 820. Each button is at least 44 px tall; the strip cells are smaller, and
    the arrow buttons beside them are the touch path.

## Limits of a blind designer

- I could not see today's screen, so no part carries a "Today:" label, and no choice cites a file
  and symbol or a "Departs from:" line. Each concept is marked Owner grant: yes for that reason.
  The "Show New: outlines" switch outlines the parts each concept adds.
- `layout.py devices` printed "unknown" for this repo. I drew the brief's sizes: 1440 with a
  pointer and 820 with touch, light and dark.
- No setup target was found in the Makefile. The mockup opens from disk and needs none.
