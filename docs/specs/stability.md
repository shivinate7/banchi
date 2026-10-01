# Screen stability — nothing moves that the person did not move

This spec holds the screen-stability rule and the mechanisms that break it. It gives one
reusable fix pattern per mechanism, the audit's findings, and how a check enforces each class.
It changes no product code. Fix lanes follow (§7).

Governing decisions: D118 (a press changes what is on screen), D50 (feedback is the product's),
D195 (same-role buttons share a width), D197 (a page is anchored to the shell inset). The
`load-stability` lane's draft decision (a loading area holds its loaded size) owns class A.

## 1. The rule

**Nothing on screen moves unless the person moved it, or it is the direct, intended result of
their own action at that spot.** A read, a timer, a font, an image, a scrollbar, a banner or a
toast never moves content the person did not touch.

- "At that spot" is the pressed control and the region it owns: a disclosure opening under its
  own header, a list re-sorting under its own sort control, a marker sliding along its own
  track. Content outside that region holds still.
- An action that needs a read holds its old frame until the new one is ready. It never draws an
  intermediate frame of another size.
- One press gives at most one layout change. Two layout changes inside 300 ms after one press is
  a defect, whatever their sizes.

## 2. How the audit measured

- **Server.** This checkout's own `make up` on port 8271, over `make demo-seed`'s store
  (`PKMNSCAN_HOME=demo`). A sale re-reads the real store, so the hero text changes as it does
  for the owner. The static demo (`make demo-static`) was used for a first pass only. Its
  recorded reads do not change the place label after a sale.
- **Browser.** Headless Chromium, 1440×1000 and 820×1000, light and dark. Every number is a
  `layout-shift` entry from `PerformanceObserver` with `buffered: true`. Entries with
  `hadRecentInput` are kept, because the rule covers what follows a press too. Each entry's
  `sources` give the moved node and its before and after rects.
- **Sweeps.** Per screen in `ROUTES`: cold load, then 4 s idle. A hover over each in-view
  control (60 at most). 25 Tab presses. One click of each in-view control (30 at most), each
  from a fresh load. The screen's own keys (`SHORTCUTS` rows) on Review, Inventory, Pricing and
  Orders. The Fulfiller's pull, undo, search and box opening.
- **Probes.** Images held 2.5 s. Fonts held 2.5 s. `/status` refused, so that the offline banner
  shows. Classic scrollbars forced (`scrollbar-width: unset` and a `::-webkit-scrollbar` width).
  Headless Chromium on macOS draws overlay scrollbars, which hide the scrollbar class. Horizontal
  overflow is `document.scrollingElement.scrollWidth - clientWidth`, read before and after each
  press.
- **Confidence.** *Confirmed*: a measured `layout-shift` entry or a measured box change.
  *Likely*: the code path is read and the shift is plausible, but the browser did not drive it.
  *Theoretical*: the mechanism exists in the code, and no route reached it.

## 3. Mechanisms and their fix patterns

Each mechanism has one fix pattern. A fix lane uses the pattern and does not write a one-off
fix.

| Class | Mechanism | Fix pattern (reusable) |
|---|---|---|
| A | A loading area draws another size than its loaded content. | Owned by `load-stability`: draw the loaded grammar from the first paint. |
| B | An action starts a read. The area unmounts or shrinks while the read is out, and grows back when it lands. | **Held frame.** Keep the old content mounted, dimmed with `aria-busy`, until the new content is ready. Never render `null` for a slot that had content. One kit hook (`useHeld(value)`) returns the last settled value while a read is out. |
| C | A conditional element (pill, chip, note, receipt, error line) mounts in flow and pushes its siblings. | **Reserved slot.** The slot always exists. Its block size comes from its content's own rule: one line box (`min-block-size: 1lh`), or a pill line (`min-block-size: var(--bn-pill-h)`). When the slot is empty, its content stays mounted with `visibility: hidden`. A kit `<Slot show>` primitive carries this. |
| C′ | A text line that can hold a pill is shorter than the pill (18 px line, 22 px pill). | **Pill line.** A new `--bn-pill-h` token (22 px, the `.bn-pill` height). Any line that can hold a pill sets `min-block-size: var(--bn-pill-h)`. `.bn-pill` reads the same token. |
| D | A banner or toast enters in flow, or pushes other overlay content. | **Overlay, not flow.** A banner is `position: fixed` over the top inset, or sits in a shell row that is always reserved. The toast stack is anchored at the far end. A new toast enters at the anchor, and the existing toasts hold their places. |
| E | Live text changes length or wrap (counts, statuses, names, captions), and its siblings move. | **Fixed line box.** A count has `.tnum` and `min-inline-size: calc(var(--digits) * 1ch)`. A one-line status has `white-space: nowrap` and `text-overflow: ellipsis` in a fixed or `minmax()` track. A toolbar that can wrap reserves its wrapped height, or moves its optional items into an overflow slot. |
| F | The document scrollbar appears or goes away as height crosses the viewport. | `scrollbar-gutter: stable` on `html`. One line in `base.css`. |
| G | A web font swaps in (`font-display: swap`, no preload, no metric fallback). | `<link rel="preload">` for the latin woff2 of each of the three faces. Add a metric-matched fallback `@font-face` (`size-adjust`, `ascent-override`, `descent-override`) for Inter, Manrope and JetBrains Mono. |
| H | An image without an intrinsic box grows when its bytes arrive. | `aspect-ratio` (or `width` and `height` attributes) on every `<img>` or on its frame. The kit's photo frames already do this. |
| I | A transition on a layout property (`width`, `height`, `max-width`, `top`, `left`, `margin`, `padding`, `grid-template-*`) moves siblings on each frame. | Animate `transform`, `opacity`, `clip-path`, color or `box-shadow` only. A fill bar uses `transform: scaleX()`. An indicator uses `translate`. The rail fold's `grid-template-columns` is the one exception. The person asked for it, and it is their action at that spot. |
| J | A measurement (`ResizeObserver`, `getBoundingClientRect`) picks a layout after the first paint. | **CSS decides layout.** A container query (`@container`) replaces a JavaScript width check, so that the first paint is already correct. |
| K | A hover or focus style changes border width, padding, font weight or size. | Change color, `box-shadow`, `outline` or `transform` only. |

## 4. Findings

`CLS` is the `layout-shift` value. `px` is the largest move of a source. The width is the
viewport. Each row names the element by its class.

### 4.1 Load time (class A): owned by `load-stability`, except S1

| # | Screen | Shift | Note |
|---|---|---|---|
| A1 | Home | 0.08 at 1440, 0.13 at 820 | `.home-grid2` and `.home-spine` move down 100–139 px when the foot lands. |
| A2 | Pricing | 0.03 at 1440, 0.05 at 820 | `.pricing-row` grows 81 px and moves 399 px. |
| A3 | Graveyard | 0.06 at 1440, 0.10 at 820 | `.bn-page-body` moves 128 px. |
| A4 | Sales | 0.05 at 1440, 0.04 at 820 | The podium thumbnails grow 187–292 px. |
| A5 | Orders | 0.008 at 1440, 0.012 at 820 | `.bn-page-body` grows 493–509 px. |
| A6 | Review | 0.004 at 1440, 0.005 at 820 | `.bn-page-body` moves 8 px. |
| A7 | Codes | 0.0004–0.001 | `.bn-head-actions` moves 135 px across. |
| A8 | Inventory, 820 | 0.03, then 0.17 at about 2.6 s | `.browse-details` moves 138 px, then 662 px. This is a late tail. A 3 s window catches it. |
| **S1** | **Fulfillment** | **0.34 at 1440, 0.51–0.59 at 820** | **Not owned.** `app/tests/routeExclusions.ts`'s `EXCLUDED_FROM_SWEEP` leaves `#/fulfillment` out of the ROUTES sweep, so the load-shift spec never opens it. The loading frame ("Getting the cards." and five skeleton bars) has another shape than the loaded page. `.ff-browse` moves 352 px up and shrinks 438–528 px. `.ff-search` moves 50 px. Confirmed. Fix: class A pattern on `Fulfillment`. |

### 4.2 After the first paint

| # | Screen | Trigger | Element | Class | Conf. | Shift | Fix pattern |
|---|---|---|---|---|---|---|---|
| S2 | Orders | Select a buyer, or press Walk | `ul.orders-walk-list` grows 403 px. `li.orders-walk-group` moves 281–633 px. At 820 the walk's position bar and card actions move 128 px across. | B, and J at 820 | Confirmed (shift); likely (J) | 1440: 0.05–0.21. 820: 0.38, then 0.21 | Held frame for the walk plan. A container query replaces `setNarrow`, the `ResizeObserver` in `Orders.tsx` that switches the walk at 560 px. |
| S3 | Inventory | Click a box in the box rail | `.browse-band`, photo frame and `.browse-details` move −28 px, then +29 px, in two frames 8 ms apart. At 820 there are three steps: −137, +104, +180 px. | B | Confirmed | 1440: 0.13–0.14. 820: 0.16–0.19, then 0.04–0.06, then 0.03 | Held frame for the card pane while the box read is out. |
| S4 | Inventory, 820 only | Step card to card (← / →, or a row click) | `.card-locations` unmounts for about 210 ms while the copies read is out. `.browse-band` shrinks 527→347 px, and `.browse-details` moves −180 px, then +180 px. At 1440 the copies sit beside the photo, so the band does not change height. | B | Confirmed (frame by frame) | 0.031 twice for each step | Held frame in `CardLocations`: keep the last copies mounted while the read is out. |
| S5 | Review | Open the lookup (`L` or the Search button), and close it (Esc) | `.review-actions` and `.review-tray` move +94 px, then −158 px, 8 ms apart. Esc moves them +65 px. `CatalogPanel` replaces the candidate list in flow. | B | Confirmed | 0.008 + 0.017 (key). 0.003 + 0.006 (click). 0.005 (Esc) | Held frame, and the actions stay at a fixed place under the stage. |
| S6 | All screens | The server goes away, then comes back | `.bn-banner` mounts in flow above `.bn-view` (sticky, not fixed). The whole view moves 44 px down, then up. The person did nothing. | D | Confirmed | 0.0255 each way | Overlay, not flow. |
| S7 | 8 of 12 screens, classic-scrollbar systems | Data lands, or the route changes between a short and a long screen | The document gains or loses a 15 px scrollbar. `.bn-head-actions` and other right-aligned or centered content moves 9–15 px across. The routes are Home, Pricing, Orders, Sales, Inventory, Graveyard, Fulfillment and Capture. Codes goes the other way. | F | Confirmed (bars forced) | dx 15 px; CLS up to 0.09 with A1 | `scrollbar-gutter: stable`. |
| S8 | Inventory, list toolbar | Tick a row; toggle "In stock only" | Tick mounts "1 ticked" and "clear" chips into `.browse-status`. At 820 "All" wraps to its own line, and the list moves 30 px. The toggle's count changes width (dx 60–67 px), and that also wraps "All". | C + E | Resolved | 0.019 at 1440. 0.034–0.038 at 820 | The list carries no ticks (D-cards-picked-in-manage-box), so the toolbar never gains chips. |
| S9 | Sales | Pick a month column | A "<month> only" pill row mounts above "Sold". `.revenue-podium` and `.revenue-bar-head` move 40 px. | C | Confirmed | 0.012–0.066 | Reserved slot, or the filter pill moves into the bar head that exists already. |
| S10 | Sales | Choose the "All" period | `.revenue-verdict-canceled` mounts. The podium, shelf, months and bar head move 22 px. | C | Confirmed | 0.0001 at 1440. 0.014 at 820 | Reserved slot (one line box). |
| S11 | Pricing | Any filter, such as "Held" | `.pricing-filter-note` mounts above `.pricing-list`. The list moves 42 px. | C | Confirmed | 0.015 | Reserved slot, or the note goes into the filter bar's count line. |
| S12 | Inventory, card hero (the known case) | Mark sold, or its Undo | The state `Pill` (22 px) mounts into `.browse-hero-sub`, which is an 18 px text line. The line grows to 22 px. `.browse-hero-side`, the photo frame, `.browse-band` and `.browse-details` move 3–4 px. The copy row's place label also changes ("Card 4 of 11" to "Card 4"), on one line. That change moves nothing. | C′ | Confirmed | 0.0017 for each sale | Pill line. |
| S13 | Orders, walk | Mark a copy sold (`1`), Undo (`U`), step (`↓`) | `.orders-pick-chip` moves 74 px across. `.orders-walk-pick-count` moves 26–33 px. At 820 the walk group moves 8–26 px down. | E | Confirmed | 0.0002 at 1440. 0.005–0.022 at 820 | Fixed line box for the pick count. The chip goes in a fixed track. |
| S14 | Review | Answer (`1`–`9`), or click a candidate | `a.review-position` changes wrap (height −16 px). `.review-caption-this` moves 11–53 px across. `.review-next-price` moves 4–39 px. | E | Confirmed | 0.0001–0.0066 | Fixed line box: a one-line caption with an ellipsis. Price in a fixed track. |
| S15 | Inventory, box stats | A sale, or a box switch | `.boxops-stat` siblings move 3 px when a value gains or loses a digit. A box switch moves them 61 px, but that is new content. | E | Confirmed | ≤0.005 | `min-inline-size` in `ch` for each stat value. |
| S16 | All screens | Any receipt toast | The stack is fixed, which is correct. But each new toast pushes the older ones up 86 px, and a receipt grows 132→190 px in place. | D | Confirmed | 0.003–0.012 (counted inside the overlay) | Toast stack anchored at the far end. |
| S17 | All screens | Web fonts arrive late | All 23 `@font-face` rules use `font-display: swap`. There is no preload and no metric fallback. Headings move 3–6 px (`.ff-title`, `.ff-today-num`, `.card-locations-name`). Money and notes move 1–6 px. | G | Confirmed (fonts held 2.5 s) | 0.0001–0.0015 per screen | Preload, and a metric fallback. |
| S18 | Sales | A podium thumbnail arrives | `.revenue-tile-body` moves 5 px. All other photographs on ten screens sit in fixed frames and move nothing when their bytes arrive. | H | Confirmed | 0.0001 | `aspect-ratio` on the tile thumbnail. |
| S19 | Fulfillment | Choose a card | `.ff-column` has `transition: max-width`, so the column widens over `--bn-t-slow` and its content reflows on each frame. | I | Likely | Not measured (the view changes in the same press) | No layout transition. Widen in one step, or use `transform` on the content. |
| S20 | Capture | Undo a capture | `undoNote`'s paragraph mounts in flow under the film strip. `.capture-undo-depth` mounts in the field label. | C | Likely (the headless browser has no camera) | — | Reserved slot. |
| S21 | Pricing, phone width | The slim bar's height changes | A `ResizeObserver` writes `--pricing-bar-h` into the list's bottom padding. | J | Theoretical (phone widths are off, DEBT77) | — | CSS decides layout. |

### 4.3 Clear

- **Hover and focus (K).** 0 shifts over about 600 hovers and 300 Tab presses on 13 screens at
  both widths. A CSS scan finds no `:hover` or `:focus` rule that changes a layout property.
- **Route change scroll anchor.** `App.tsx` resets the scroll with `window.scrollTo(0, 0)` in an
  effect on `path`. A frame-by-frame read after a sidebar press from a scrolled Graveyard shows
  the new screen first at `scrollY` 0. No frame shows the new screen at the old offset.
- **Layout transitions that are contained or intended.** `.browse-boxcell-bar > span`,
  `.home-box-bar > span`, `.capture-meter-fill` and `.bn-progress > span` animate `width` inside
  a fixed track. Their siblings do not move. `.position-bar-marker`, `.position-bar-cell`,
  `.position-bar-chip` and `.boxops-mark` animate `left` on an indicator along its own track.
  `.capture-pauseplay` is absolute in the camera stage. `.bn-shell` and `.bn-brand-slot` are the
  rail fold. `.home-deck-photo` animates its crop width inside its own window. These are
  intended. A lint lets them through by name (§5).
- **Intended content changes.** These presses were measured, and each move is the press's own
  result at its spot:
  - a filter or sort that reorders rows (Graveyard "Sold", Sales "Copies");
  - a disclosure that opens under its header (Fulfillment box, Inventory section fold);
  - the Sales "Custom" period, which opens its date fields under the period control.

  The Custom period moves the body 58 px. It is borderline, and the class C pattern would also
  serve it.
- **Dark theme.** The same shifts as light, at the same sizes.

### 4.4 The known sale case, raw

Inventory at 1253×1000, the real server. Mark sold on "Void Assault" (RB Origins, Section 1,
Card 4 of 11). There is one entry 13 ms after the press. Rects are `[x, y, width, height]`.

```json
{"value":0.00174,"hadRecentInput":true,"sources":[
 {"node":"div.browse-band","prev":[380,192,841,720],"cur":[380,195,841,720]},
 {"node":"button.bn-photo.browse-photo-frame","prev":[380,176,314,424],"cur":[380,179,314,424]},
 {"node":"details.bn-panel.browse-details","prev":[377,926,847,75],"cur":[377,929,847,71]},
 {"node":"p.browse-hero-side","prev":[400,156,385,18],"cur":[400,160,385,18]}]}
```

`p.browse-hero-sub` is 18.0 px before the press and 22.0 px after it. The added child is
`span.bn-pill.bn-pill-ok` "Sold" (22 px). The hero text that changes is the copy row's place
label, `span.card-locations-identity` ("Card 4 of 11" to "Card 4"). It moves nothing.

The 1238→1241 figure is the document's **scroll height**, not its width. At 1253×900 with
classic scrollbars, `scrollHeight` goes 1238→1241 and `clientWidth` holds at 1253. No scrollbar
toggles on this press. The +3.5 px is the pill line, S12. A short window can still cross the
viewport on this press, and S7's gutter covers that case.

### 4.5 Horizontal overflow at 820

| Screen | Before the press | After the press |
|---|---|---|
| Home, Capture, Review, Pricing, Orders, Shipping, Sales, Inventory, Graveyard, Codes, Fulfillment, Kit, Product history | 0 | 0 (every clicked control and every key flow) |

There are no offenders.

### 4.6 Seen in passing (not hunted)

| Screen | Element | Defect |
|---|---|---|
| Inventory, 820 | `.browse-status` "All" | Resolved by D-cards-picked-in-manage-box: the toolbar has no "All" and no tick chips. |
| Inventory, Sales, Pricing, Review, Orders at 1440 | `.bn-btn` (24–34 px), `.bn-seg-item` (24–28 px), `.browse-row` (32 px), `.browse-quiet` (24 px), `.bn-hidetoggle` (28 px) | Many desktop controls are under 40 px tall. CLAUDE.md's 40 px floor names "anything a thumb presses". Whether it binds at 1440 is the owner's call. |
| Fulfillment, box list | `.ff-box` rows | The place line ("RB Origins · Section 1 · Card 1") is set larger than the card name above it. Check whether this is intended. |

### 4.7 Counts

| Class | A | B | C | C′ | D | E | F | G | H | I | J | K |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Rows | 9 | 4 | 5 | 1 | 2 | 4 | 1 | 1 | 1 | 1 | 2 | 0 |

Class A holds 8 rows that `load-stability` owns, and S1, which no lane owns. The table holds 30
rows. S2 counts in B and in J.

By confidence: confirmed 26, likely 3 (S2's J half, S19 and S20), theoretical 1 (S21).

Top five by impact (size × how often × whose screen):

1. **S1, Fulfillment load**: 0.34–0.59 on each open of the Fulfiller's whole product. No check
   covers it.
2. **S2, Orders walk open**: 0.05–0.38, then 0.21, on each buyer.
3. **S3, Inventory box switch**: 0.13–0.19 in two or three steps.
4. **S4, Inventory card step at 820**: 0.031 twice on every step. This is the most frequent press
   in the library.
5. **S7, scrollbar toggle**: a 15 px sideways jump on 8 of 12 screens, on classic-scrollbar
   systems.

## 5. Enforcement

**Standing rule (for CLAUDE.md, The design system):** *Nothing on screen moves unless the
person moved it, or it is the direct result of their own press at that spot. A read, a timer, a
font, an image, a scrollbar, a banner or a toast never moves content (this spec).*

| Class | Check | Mechanized? |
|---|---|---|
| A | `app/tests/stability.spec.ts` (D313, nothing moves unless the person moved it). It must stop excluding `#/fulfillment`, or a Fulfillment-only case must cover S1. | Yes |
| B, C, C′, E | New rows in `app/tests/stability.spec.ts`. A press registry beside `ROUTES` (to be built, in the same spec) names each screen's primary presses and keys. The spec runs each press at 1440 and 820 and sums `layout-shift` entries including `hadRecentInput`. It leaves out sources inside the pressed control's own region and inside `.bn-toasts`. It fails a sum of 0.005 or more, and it fails two entries inside 300 ms after one press. A new screen with no registry entry fails. Exceptions are a shrinking allow list (D280). | Yes |
| D | A spec refuses `/status`, asserts the banner shows, and asserts 0 shift on `.bn-view`. A toast case sends three receipts and asserts the first toast's rect holds. | Yes |
| F | A `docs-audit` row asserts `scrollbar-gutter: stable` on `html` in `base.css`. The spec above also runs once with classic bars forced. | Yes |
| G | A `docs-audit` row asserts a preload link for each face in `app/index.html` and a metric fallback in `fonts.css`. A spec with fonts held 2 s asserts a sum under 0.001. | Yes |
| H | A spec holds images 2.5 s on every route and asserts 0 shift. A static scan of `<img>` cannot see a frame class, so the browser is the check. | Yes (in the browser) |
| I | A `docs-audit` row scans `app/src/**/*.css` for `transition` or `transition-property` that names a layout property. The allow list names the contained and intended selectors in §4.3, and it only shrinks. | Yes |
| J | No lint. A `ResizeObserver` or a measured width can be correct (`Lockup`, the tooltip). The stability spec catches the effect. | Through the effect only |
| K | A `docs-audit` row refuses a `:hover`, `:focus` or `:active` rule that sets a layout property. It is clean today. The row must first go red on a planted case. | Yes |
| C (static) | A lint for "a conditional element in flow with no reserved slot" is **not proposed as a gate**. The scan finds 204 `cond ? <El/> : null` mounts in `app/src` (47 that look like status). It cannot read whether the parent reserves the space. It would flag correct code and teach readers to skip it. The browser spec is the check. | No (static); yes (in the browser) |

**NOT MECHANIZED:** whether a measured move is "the direct result of the press at that spot". A
machine can bound the region by the pressed control's own subtree, but it cannot tell an
intended disclosure from a push. The registry's allow list holds that judgment, one named entry
for each press.

Trust a new guard only after it goes red on the defect it guards. The stability spec
must fail on today's `main` at S2, S3, S4, S8, S9, S11 and S12 before any fix lane lands.

## 6. Out of scope

- Phone widths (390). DEBT77 turns the phone specs off. S21 is listed and not measured.
- Capture with a live camera. S20 is read from the code.
- Codes is dormant. It was swept and holds only A7.

## 7. Fix lanes, ranked

1. **Held frame on re-read (B; S2, S3, S4, S5).** This is the largest shift, on the most
   frequent presses. It adds a kit `useHeld` hook, and each call site keeps its last content
   while a read is out. Orders' `setNarrow` becomes a container query. Files:
   `app/src/kit/index.tsx`, `app/src/BoxBrowse.tsx`, `app/src/CardHero.tsx`,
   `app/src/CardLocations.tsx`, `app/src/Orders.tsx`, `app/src/Orders.css`,
   `app/src/OrdersWalkPane.tsx`, `app/src/ReviewQueue.tsx`, `app/src/ReviewQueue.css`.
2. **Shell and globals (D, F, G, H, I; S6, S7, S16–S19).** It also takes S1 if `load-stability`
   does not. These are mostly one-line changes, and each reaches every screen. Files:
   `app/src/base.css`, `app/index.html`, `app/src/fonts.css`, `app/src/App.tsx`,
   `app/src/App.css`, `app/src/kit/toast.tsx`, `app/src/kit.css`, `app/src/Fulfillment.tsx`,
   `app/src/Fulfillment.css`, `app/src/Revenue.css`, and the `docs-audit` rows for F, G, I and K
   in `scripts/`.
3. **Reserved slots and live text (C, C′, E; S8–S15, S20).** This adds the kit `<Slot>`
   primitive, the `--bn-pill-h` token and a `.bn-count` utility, then moves each call site onto
   them. Files: `app/src/tokens.css`, `app/src/kit.css`, `app/src/kit/index.tsx`,
   `app/src/CardHero.tsx`, `app/src/BoxBrowse.tsx`, `app/src/BoxBrowse.css`,
   `app/src/BoxOps.css`, `app/src/Revenue.tsx`, `app/src/Pricing.tsx`, `app/src/Pricing.css`,
   `app/src/Orders.tsx`, `app/src/ReviewQueue.tsx`, `app/src/CaptureScreen.tsx`.
4. **The guard (§5).** Each fix lane adds its own rows to `app/tests/stability.spec.ts` (D313,
   nothing moves unless the person moved it), red on `main` before its fix and green after. A
   lane deletes its own entries from `app/tests/stability-allow.json`. Lanes 1–3 run in parallel.
