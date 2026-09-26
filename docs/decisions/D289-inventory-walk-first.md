## D289 — The walk list is the rail's main part, and 720 is a desk

**The review's findings and the owner's rulings, 2026-09-23.** This entry amends the rail half
of D40 (the screen is three columns: the box, the card, and where its copies are). D40 put the
box list, the box card and the walk in one column. It did not say which one gets the height.

### What the review measured

- **The walk list was a 183px window at 1440x900** (UX-206). The search, three selects, the box
  list, the box card and a two-line toolbar took the rest of the column.
- **The rail ran past the bottom of the window** (UX-227). The rail is sticky. At rest it sits
  under the page head, so a rail as tall as the window ended below the fold. A step to the last
  card of a box scrolled the list to its end, and the row stayed out of view.
- **At 720 the page drew the phone** (UX-245, UX-187). The owner works in a half-width window.
  The list, the filters and the box went into a bottom sheet, and the card's place fell below
  the fold.

### The rule

1. **The walk list is the tallest part of the rail.** The box list holds three and a half boxes
   and scrolls. The half row shows that it scrolls. The filters sit behind one press on the
   search's line. The walk's toolbar is one line at 1440. The key legend is gone, because the
   ? sheet lists the keys.
2. **The rail fits the window at rest.** `BoxBrowse.tsx` measures the rail's top at rest, and
   the rail's height is the window less that top.
3. **720 is a desk.** The lane's breakpoints move from 767 to 639, with the shell's (the
   owner's Q2 ruling). From 640 up, the rail sits beside the card.
4. **A one-column card pane says the card's place under its name.** The copy row that also
   says it sits under the photo, below the fold.

### What this protects

D40 protected a screen that shows the box, the card and its copies at once. That stays. This
entry decides only which part of the rail gets the height.

### What is still open

- **Below 1280 the walk's toolbar is two lines.** The rail is 268px there, and Collapse all,
  Hide sold and tick shown need about 285px. The icon buttons of the kit-icons lane may close
  the gap.
