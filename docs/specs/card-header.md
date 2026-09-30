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
