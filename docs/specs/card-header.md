# Card detail: the top of the page

Status: design only, no product code. The sheet is `docs/specs/card-header/sheet.html`
(`?theme=dark` for dark). It links `app/src/tokens.css` and `app/src/kit.css`. It adds only
layout, in `--bn-*` tokens. Each frame is the card pane, not the viewport. A 1440 viewport gives
an 820px pane. An 820 viewport gives a 410px pane. Both were measured in the running app. The
photo in the sheet is the demo store's drawn photograph, a stand-in for the LeBlanc card.

## The problem

The top is drawn by `CardHeroHead` and `CardPane` in `app/src/CardHero.tsx`. The Copies head is
drawn by `CardLocations` in `app/src/CardLocations.tsx`. At a 1440 viewport:

- The title block (name, number line, rarity, menu) is one block. The photo and the Copies block
  form a second block under it. Nothing joins them.
- The Copies heading, the three counts, the reading age and the sent line are their own header
  inside the band. The band is a grid of photo (34%) and copies. The copies column has a tall
  empty area at the top right. The counts sit at the upper left of it. The sent line is pushed
  right, alone.
- "Epic" gets a whole chip row (`.browse-hero-chips`) for one 22px pill.
- The word "Copies" names what the rows below already show. It earns no height.
- At an 820 viewport the photo stacks full width above everything. The counts land about 640px
  down the pane.
- The menu button is 28px with a 40px hit pad from the kit. That stays.

Facts to keep: name, number, game, rarity, copies, in the boxes, live (with red dot), when it was
read, sent, ceiling, the menu. One fact is a duplicate: the heading word "Copies". The count
"7 copies" says it. All three directions drop it.

## A. Rail

The photo becomes a left rail (250px) that runs the full height of the pane. The right column is
one stack. First, the name and the menu. Then the number, game and Epic pill on one line. Then a
ruled counts strip: 7 copies, 5 in the boxes, and live with its dot and "read 2 days ago". Then
the sent and ceiling line in small type. Then the copies. The header and the copies share one
column and one left edge, so they read as one block. The empty band cannot exist, because only
content sits beside the photo. At 410 the rail shrinks to a 116px thumbnail beside the title. The
strip then runs full width.

Trade-offs: the photo stays large on desktop. The owner uses it to compare the physical card. The
sent and ceiling line stays a separate small line, quieter than the counts. At 410 the thumbnail
leaves a short gap under a one-line title.

## B. Masthead

One full-width header. The name, number line and pill are on the left. The three counts are on
the right, and the menu is at the far right. Under it is a full-width meter row. It says "5 live
of 5 allowed, 7 sent". The reading age is at its right. A `bn-progress` bar fills live against
the ceiling. The photo and copies sit under that, as today. This is the closest match to the
owner's words: the counts are in the header. The meter turns "At the ceiling of 5" from a stray
sentence into a picture. The bar is neutral, not green. A full bar is not read as good or bad.

Trade-offs: this header is the tallest of the three. The photo still sits under it and gets a
smaller share of the pane. At 410 the counts drop under the title. The photo stacks over the
copies, as today.

## C. Ledger

The photo shrinks to a 140px leading thumbnail (tap to zoom, as now). The facts become four ruled
rows of 40px. They are Copies 7, In the boxes 5, Live on TCGplayer with the dot and "read 2 days
ago", and Sent 7 with "At the ceiling of 5". Each fact has a label and one number in one column.
The ceiling sits with the sent figure it explains. The copies list takes the full pane width.

Trade-offs: this is the shortest top. It is the tidiest at 410, where it matches the 820 frame.
The copies rows get the most width. It gives up the large photo. That is a real loss if the owner
checks the card against the photograph on this screen. Big numerals are gone, so the counts lose
weight.

## Recommendation

A, the Rail. It fixes the named defect directly. The photo column runs the full height, so the
band has no empty top right. The counts join the title in one column. It keeps every fact and
the large photo. The structural change is small. `CardPane` places `CardHeroHead`, the photo and
the copies head in one grid. `CardLocations` draws the strip and the sent line in place of its
own heading. Choose B if the owner wants the counts to the right of the title on one line.
Choose C if the photo is not needed at size.

Build notes for A:

- Rarity, finish and the state pill join the meta line. The `.browse-hero-chips` row is deleted.
  A card with many chips wraps that line. The sheet does not show that case.
- `.browse-band` has a fixed height (D118, one height for the whole walk). The rail keeps it.
  The copies list scrolls inside, as today.
- The word "Copies" is removed. A screen reader gets the list name from an `aria-label` on the
  list.
- The sheet does not show three cases: the re-rank chip slot, the "sold here since" split, and
  a card with no listing (two counts, no sent line). Each fits the strip. The strip must keep
  the always-rendered slot for the re-rank chip.

Unmeasured: how often the owner reads the photo on this screen. Also unmeasured: how many copies
a typical card has. The sheet shows two rows and "5 more copies".

## Second round: everything in the band above the photo

New constraint from the owner: all the copies facts fit in the band that the title block takes
today. The facts are the title, number, game, rarity, the three counts, the read age and the
sent and ceiling line. The band is full width. The photo and copies sit under it. The copies
take all the remaining height. The copy rows now use the real card ruler. `PositionBar.css` is
linked, and the markup is `PositionBar.tsx`'s own. That gives the box strip, ticks every 5,
numbers every 10, the blue number chip, and Back and Front written once. A to C use the same
rows.

### D. Inline

Two lines. Line one has the name, then number, game and Epic pill. Line two is the counts as
one sentence of inline facts. It has 7 copies, 5 in the boxes, live with its dot and read age,
and 7 sent at the ceiling of 5. This is the shortest band, about 90px. The photo (220px) sits
beside the copies. At 410 a thumbnail leads the title and the facts wrap to three short lines.
Trade-off: the counts lose their size. They read as text, not as figures.

### E. Cluster

A two-line title block with a 56px thumbnail. The three counts sit at the right of the same
band as a cluster. The read age is under live. The sent and ceiling line is under the cluster.
The copies run the full pane width, which gives the ruler the most room. Trade-off: the large
photo is gone. Tap the thumbnail to zoom. At 410 the cluster drops to its own row under the
title.

### F. Stat bar

Title and meta on top. Under them is one compact bar (40px) of three counts. At its end is the
ceiling as a meter. It says "7 sent, At the ceiling of 5" and shows a bar that fills live
against the ceiling. The bar is neutral, not green. The photo sits beside the copies.
Trade-off: the band is about 130px, taller than D. At 410 the bar wraps to three rows.

### Pick for the second round

F. It is the only pass that keeps the counts as figures and turns the ceiling into a picture.
The band stays close to today's height. The photo stays large. Choose D if the shortest band
matters most. Choose E if the copies list should get the full width.

## Third and fourth rounds: F2 and F3

F2 takes the white space out of F. It uses smaller spacing rungs and the menu sits on the title
line. The bar fills the width. The photo and the copies both start directly under the band. The
"hidden" line under the copies list is folded into the bar. That line only reports the departed
copies that the hide-sold setting folds away, and it is not a press today. Whether it should
become one is open.

F3 re-ranks the figures. It is F2 with two lead figures and quieter side facts.

- Lead, equal weight: "in the boxes" (`group.on_hand`, the true inventory) and "live on
  TCGplayer" with the red dot and the read age. The ceiling meter sits under the live figure, so
  it stays tied to live.
- Side, quieter and equal to each other: "captured", "hidden", and "sent" with the ceiling.
  "Captured" is every copy the store holds for the SKU. That is `group.copies.length`, sold and
  moved copies included, the same meaning as the box census. It replaces the old bare "copies".
  "Hidden" is the departed copies that the hide-sold fold removes from the list.
- The sheet's numbers agree with those meanings: 5 in the boxes and 3 departed give 8 captured.
- Separators are drawn in CSS (D218). At 410 the side facts drop to one row under the lead
  figures.
- Trade-off: the sent and ceiling line is now a small fact, not a headline. The meter carries
  the ceiling for the reader who glances.

### Pick

F3. It puts the two figures the owner acts on at the front, with equal weight. It keeps every
fact and gives the ceiling a picture next to live. The band is about 70px tall under the title.
Choose F2 if the owner wants the counts as a flat row of equal cells.
