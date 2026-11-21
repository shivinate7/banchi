# Tombstone slips hold the slot (idea mockup, nothing ships)

A thermal printer prints one slip per sold card in walk order. The card leaves with the stub, and the slip's tall half
stands in its slot until the next re-capture of that section scans it out.

**Click through.** Open `tombstone-slips.html` from disk. The State tabs, or `#state=run|normal|neighbor|return|mystery|cancel|slab`,
add `&t=dark` or `&t=light`, `&scale=2`, and `&thumb=off`, `&tick=off`, `&band=off` to hide an option. "Simulate a Scan" ticks the next slip.

**Reached from.** Orders (the print run follows each fetch) and Capture (Clear Slips, before a section is re-captured).
Nearest specs: `docs/specs/order-walk-plan.md` (walk order, neighbor lines) and `docs/specs/order-flow.md` section 4.1 (the label).

- Departs from: D58 (a card number counts on-hand cards, `pipeline.join.Position`) — a standing slip counts as a card until it is cleared. Paper cannot refresh, so without this every number printed behind a slip is off by one per pull.
- Departs from: Cards to Pull's Pull then Mark sold (`store.orders.record_pull`) — a card counts pulled when its slip prints (plan question 3).
- Departs from: D83's "tombstone" (a moved card's record) — screens call the paper a "slip", so one word keeps one meaning.

## Design choices

1. **Order number reversed out of the black band.** Gain: the slot reads from above without lifting the slip. Lose: more heat on the band, more curl. Pick: yes (hide: `band=off`).
2. **The slip prints Banchi's label, "Section 7, Card 12 of 50", not the plan's box-wide "POS 42 of 118".** Gain: the same words as every screen (D260). Lose: needs the D58 departure above. Pick: yes. Owner grant: yes.
3. **Dithered thumbnail, version 2 only.** Gain: a picture to check against. Lose: about 45 mm more paper and a slower print per slip. Pick: version 2 (hide: `thumb=off`).
4. **"Neighbor off" tick box on the stub, version 2.** Gain: a moved section goes first at re-capture. Lose: needs a stub scan at packing to be read. Pick: version 2 (hide: `tick=off`).
5. **The neighbor lines and the ruler are the finding aid, not a count.** Gain: the Fulfiller matches two names, as Cards to Pull already shows (`CardLocations`). Lose: none new. Pick: yes.
6. **Clear Slips is a step on Capture, owner side.** Gain: re-capture is the owner's rig. Lose: if the Fulfiller clears, it needs his floors (20 px text, 44 px targets). Pick: owner side.
7. **Start Re-Capture waits until each slip is scanned; the disabled button says why.** Gain: no slip is captured as a card. Lose: one more gate. Pick: yes.
8. **A mystery slip goes to Review with its slot photo, and the row offers "Open in Review".** Gain: no guess about where the card went. Lose: one more Review question. Pick: yes.
9. **No slip in a slab box.** A slab stands about 135 mm, so a 100 mm slip sits 35 mm under the tops and shows nothing. Gain: no wasted paper. Lose: the slot is held by the stub and cert check only. Pick: stub only.
10. **The slip paints two local colours, `--slip-paper` and `--slip-ink`, in both themes.** Gain: it reads as paper. Lose: two literals outside `--bn-*`. They never reach `app/src`, since a built slip is printed. Pick: yes.
11. **Every QR is a hatched box marked "QR FAKE".** It holds no code.

## Owner questions (from the plan)

1. Is a position a count from the divider? Read: it is a fixed index (D10) with a label that counts on-hand cards (D58). So the neighbor names do the finding, and choice 2 must count standing slips. Owner grant: yes.
2. Do slabs and valuable cards sit inside long-box sections, or in their own box? The mockup assumes their own box (choice 9).
3. Does a card count as pulled when its slip prints, or when its stub is scanned at packing? Plan recommends print, with cancel strips. Owner grant: yes.
4. The paper's name: keep "tombstone" for the idea, and "slip" on every screen?

## Verdicts

- 1440 light (`tombstone-slips-1440-light.png`): pass. The strip, side view and Clear Slips sit in two rows with no overflow.
- 820 dark (`tombstone-slips-820-dark.png`): pass. The views stack, the shell folds to its rail, labels stay readable.
