# Card detail panel

Status: built. Two screens draw it from one home: `#/inventory` and the `#/orders` walk. The sheet is `docs/specs/card-detail/sheet.html` (`#light` or `#dark`).
The renders sit beside it: `pane-820-*.png`, `pane-410-*.png`, `live-states-*.png`.

## The direction: one band, then the hand

The panel has two parts.

1. **The band.** It is one block across the full width of the panel. It holds every fact about the card and its copies.
2. **Below the band.** The photo, and the copies list. The list takes all of the remaining height.

### The band

- Left column:
  - The title on line 1.
  - The meta line on line 2: number (mono), set, game, then rarity and finish as outline pills on the *same* line.
    No row holds rarity alone.
  - The side facts on line 3: `Captured 8`, `Hidden 3` and `Sent 7`. All three have the same size and weight.
- Right column: the two lead figures. They have equal weight, and a hairline divides them.
  - **Stored.** The copies in the boxes.
  - **Live.** The label line holds the state dot, the label and the read age ("2d ago", sentence case).
    The figure itself is plain ink. A recent reading is calm: the dot is `bn-dot-live`, 6px, with no pulse.
    Under the figure is the ceiling meter: one cell for each listing that the cap allows, filled up to the live count.
    The end of the meter says **Cap 5**, so the meter says what it measures, and the ceiling reads with Live.
- At pane 410 the band stacks. A hairline puts the two figures side by side under the identity lines.
- Labels are one word each: Stored, Live, Captured, Hidden, Sent, Cap.

### Why

- The old header spent rows on the name, the number line and a chip row. The figures sat beside the photo, under a
  "Copies" heading, and read as facts about the list. The figures are facts about the card, so they go in the band
  with the card.
- Two lead figures answer the two questions the owner opens the panel with: "how many do I hold" and "how many are
  for sale". The side facts are history and are quieter.
- The meter replaces the headroom sentence ("Room for 2 more live"). The eye reads it as a count against a ceiling,
  and its end names the ceiling.

### A copy row

The row keeps every fact that the built row has:

- the address: box, section, and "Card N of M";
- the neighbor line. It has no words (owner ruling). It runs the same way as the ruler:
  "← **Bellows Breath** [4] **Hextech Anomaly** →".
  - The left arrow points to the back, and the right arrow points to the front.
  - [4] is this copy's own number chip, the same accent chip as on the ruler pin. It sits between the two neighbors.
  - At the end of a box, an outline BACK or FRONT pill takes the place of the name and its arrow.
  - Each "arrow + name" pair is kept together on one line;
- the section strip;
- the card ruler: ticks every 5, a number every 10, the edge numbers, the filled card cell and the pin;
- BACK/FRONT, written once under the ruler.

There are two changes to the ruler:

- **The number chip is centered on the pin.** The built chip sits beside the pin and flips past the middle.
  The new chip is clamped inside the ruler at both ends (card 1 and card 42 in the sheet).
- **A tick number within 2 cards of the pin is not drawn.** The chip names that place.

### The actions: one primary, never a wall

The code makes Mark sold the act that matters. Walk-in sales are recorded here (`OwnerRows` rule 3), and it is the
only act with a worded primary form (`Inventory.tsx` `renderAction`). Retire and Move open a dialog.

Owner ruling: no copy is chosen or preselected (`OwnerRows` rule 2 stands). Mark sold is the same control, at the
same weight, on every row.

- **Mark sold** is a worded 40px `bn-btn`, 128px wide, with accent ink on the `--bn-accent-tint` ground. It has no
  fill and no shadow. On hover the ground goes to `--bn-accent-tint-2`.
  It is the one colored control in the row, so it is clearly the primary act. Three tinted buttons do not make
  a wall of accent.
- **Retire** and **Move** are bare `bn-icon-btn` icons at 40px, in ink-3.
- All targets are 40px or more.
- The actions are the foot of the row, right-aligned under BACK/FRONT, at every width. No text line shares a line
  with a 40px control, so the gap between the lines is the same on every row.

## Build checklist (one Sonnet lane)

Run `make orient` on each file before editing it. Look at the result at 1440 and 820, in both themes, against the
PNGs.

1. `app/src/CardHero.tsx` `CardHeroHead`:
   - Put the finish and rarity pills on the meta line (`browse-hero-sub`). Delete the `browse-hero-chips` row.
     The state pill and `preChips`/`postChips` move to that same line.
   - Turn the head into the band grid: identity on the left, figures on the right, and one column under 520px of
     pane width.
2. Move the figures out of `CardLocations.tsx` `OwnerRows` `card-locations-stats` and `card-locations-counts`, into
   the band. Pass `group` and `listedAt` to the head from `Inventory.tsx`, which already holds both.
   - Stored = `group.on_hand`.
   - Live = `forSale(group.listed.live, group.sold_here)`, with `ReadingAge` shortened to "2d ago".
     Keep "N when read / N sold here since" as the title text of the Live figure.
   - Captured = `group.copies.length`. Hidden = the `hidden` count from `OwnerRows`. Sent = `group.listed.pushed`.
     Cap = `group.listable`.
   - A group with a null `group.sku` gets no listing figures in the band. Keep that rule.
   - Delete the `card-locations-hidden` line. The band says Hidden now.
3. The ceiling meter:
   - Make it a new kit part in `app/src/kit/` (`Meter`: cells, filled count, end label).
   - Add it to `#/gallery`.
   - Draw over-cap as filled cells plus a warn end label ("Cap 5, 1 over"). Do not add cells past the cap.
4. The Live dot:
   - The dot sits in the label line, 6px, not on the figure.
   - A recent reading: `bn-dot-live` with no pulse. Add a kit modifier (for example `bn-dot-still`) to stop the
     pulse, and do not change `bn-dot-live` itself.
   - A reading 3 days old or more: `bn-dot-warn`. **Provisional:** the owner may drop the amber state.
   - An unread figure is a quiet dash, with no dot.
5. `app/src/PositionBar.tsx` and `app/src/PositionBar.css`:
   - Center `.position-bar-chip` on the pin, and clamp it inside the ruler.
   - Delete `data-flip`.
   - Do not draw the tick number within 2 cards of the pin.
   - Keep the height of the block the same in every state (D118, a press moves nothing).
6. `app/src/PlaceNeighbors.tsx`:
   - Draw "← back-name [N] front-name →": CSS arrows in ink-4, and the copy's number in the ruler's chip style.
   - No words on screen. Keep the spoken `aria-label` as it is.
   - Each "arrow + name" pair is one unbreakable group.
   - Draw the end-of-box word as a `bn-pill-sm bn-pill-outline` chip, with no arrow.
   - The line spans the full row, under the address.
7. `Inventory.tsx` `renderAction` row form:
   - Use the same control on every row: a worded `Button` "Mark sold" with the `sold` icon, accent ink and a tint
     ground. It shares one width across the rows (D195, same-role buttons share a width).
     Add the tint form as a kit button variant, not as a local style.
   - Retire and Move stay `IconButton size="xl"`.
   - Put the actions in a right-aligned foot row under the ruler, at every width.
   - Add no chosen or preselected row.
   - `app/tests/button-stack.spec.ts` may measure this row. Read it, and update it to the new form.
8. `app/src/BoxBrowse.css` `.browse-band`: the photo is one column, and the copies list takes `flex: 1` and scrolls.
   At a narrow pane the photo stacks above the list at 180px wide.
9. Use `--bn-*` tokens only. Draw every separator in CSS (D218, a typed dot is a defect).
   Run `cd app && npx tsc --noEmit`, `make docs-audit` and `make design-check`.

## Open

- The amber state at 3 days is provisional (item 4).
- The brief's data has 5 stored but draws 3 copy rows. The sheet draws what the brief names. In the product, the
  rows count every drawn copy.
- A short copy list leaves empty height under the photo and under the list at pane 820.
- At 410 the photo is 180px wide and centered, so there is empty space on each side of it.
