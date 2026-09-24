# Phone, touch and accessibility

Target: the published demo (`https://shivinate7.github.io/banchi/`, main at PR #454), 2026-09-23.
Phone: 390x844 and 360x740, `isMobile` and `hasTouch`, light and dark. Accessibility: 1440x900 and
390x844, light and dark, axe-core injected per route. Screenshots were not kept.
Scripts: ACC probe script, not kept, ACC probe script, not kept. Raw data: ACC scratch file, not kept.

## Grade matrix
| Route | Grade | One-line reason |
|---|---|---|
| `#/` Home | B | No side scroll, and all targets are 40 px or more. Two stage notes end in an ellipsis at 390, and a key chip shows on a phone. |
| `#/capture` Capture | C | No h1 at phone width, a prohibited `aria-label` on a `<p>`, and keycaps on a touch screen. The Run panel leaves an empty column at 390. |
| `#/runs` Runs | B | Fits, with large targets. Its sheets fit and close. The run list has no heading to jump to. |
| `#/review` Review | HELD | Main state notes are below. |
| `#/pricing` Pricing | D | Scrolls sideways at 360. A sticky panel covers a third of the phone screen. Worklist details read at 3:1, and some targets are under 40 px. |
| `#/orders` Orders | HELD | Main state notes are below. |
| `#/shipping` Shipping | C | A 37,000 px phone page, an 18 px tall disclosure, and no tab-bar location. |
| `#/revenue` Sales | D | Product names are cut through their letters at 390 and 360. At 360 the table loses its header and its last column. |
| `#/inventory` Inventory | HELD | Main state notes are below. |
| `#/graveyard` Graveyard | B | Only the demo refusal state draws. That state fits and reads well. |
| `#/codes` Codes | B | Fits, and the read sheet fits and closes. The empty-state title is not a heading. |
| `#/fulfillment` Cards to pull | B | Large type and targets, and a clean axe run. The search placeholder is cut at 390. |
| `#/gallery` Kit | C | The kit's own tabs, fields and table fail axe and do not fit a phone. A screen that copies them gets the same defects. |
| `#/product` Product history | C | The screen is fine. No link, palette entry or nav row reaches it. Only a typed URL does. |

## Findings

### ACC-01 Pricing scrolls sideways at 360 px
- Severity: S2
- Screens: `#/pricing`
- Where: 360/light and dark (390 is clean)
- Repro: open `https://shivinate7.github.io/banchi/#/pricing` at 360x740 with touch. Scroll to the price-rule strip under "Ready to write".
- Seen: `scrollWidth - clientWidth` is 6 px. The "Custom" option of the rule strip runs past the right edge. The tab bar and the Mark down and Clear sheets then measure 366 px wide on a 360 px screen. The page drifts under a thumb.
- Shot: ACC-01, screenshot not kept.
- Direction: the four-option rule strip fits 360 px, so the page never pans sideways on a small phone.
- Component: `app/src/Pricing.tsx`, the price-rule `Segmented` (`.bn-seg`) above "Holding" and "Load trends".
- Annotation: no decision covers this. D117 (the thumb floor is the kit's) and CLAUDE.md name 390 as the smallest checked width, so 360 has no reader. prior: none, the 2026-09-20 review did not check phone widths.

### ACC-02 Pricing's sticky "Ship this run" panel covers a third of the phone screen
- Severity: S2
- Screens: `#/pricing`
- Where: 390 and 360, both themes
- Repro: open `#/pricing` at 390x844 and scroll the worklist.
- Seen: `aside.pricing-ship` is 174 px tall. It sticks above the 64 px tab bar, under the 52 px top bar. Chrome takes 290 of 844 px (34%) at 390 and 290 of 740 px (39%) at 360. It covers the "Above the cut-off" heading, the "21 rows" line and whole worklist rows as they pass under it.
- Shot: ACC-02, screenshot not kept.
- Direction: on a phone the write action stays in reach without holding a third of the screen. One example is a one-line bar that opens on a tap.
- Component: `app/src/Pricing.tsx`, the `aside.pricing-ship` block (split in two, hold to, Write the import file).
- Annotation: caused by D208 (one verdict on Pricing). Its phone rule stacks the ship bar full width: split checkbox, cap field, Write button. That makes the bar 174 px tall, and it stays sticky. D208 argues the stack, not its cost in screen height. prior: none, phone width was not checked on 2026-09-20.

### ACC-03 Sales table cuts product names through the letters on a phone
- Severity: S2
- Screens: `#/revenue`
- Where: 390 and 360, both themes
- Repro: open `#/revenue` at 390x844 and scroll to the product table under the search field.
- Seen: every two-word name ("Mirror Image", "Public Execution", "Bellows Breath") shows its second line cut in half. The name cell's bottom rule sits in the middle of the row. At 360 the "Last sold" year is cut at the right edge. The header row scrolls away, so the numbers have no column names. The table's own scroller overflows 8 px at 390 and 38 px at 360.
- Shot: ACC-03, screenshot not kept.
- Direction: a full product name reads on a phone. Every column keeps its label while the owner scrolls a long table.
- Component: `app/src/Revenue.css`, the rule `.revenue-table td:nth-child(2)` (a `-webkit-box` line clamp on a table cell). `app/src/Revenue.tsx` draws the table.
- Annotation: no decision covers this. The two-line clamp is a local defect fix in `Revenue.css`, not a decision. D217 (Sales becomes a tool) governs the table and argues only the header overflow at 390. prior: none, sales.md did not check 390.

### ACC-04 The phone drawer is not modal
- Severity: S2
- Screens: every owner screen (the shell)
- Where: 390 and 360, both themes (measured, not seen: focus does not show in a screenshot)
- Repro: open `#/` at 390x844 and tap the menu button (top right). Then press Tab three times with a keyboard.
- Seen: focus stays on the Menu button when the drawer opens. The drawer (`role=dialog`, "Screens") has no `aria-modal`. The page behind is not `inert` or `aria-hidden`. Three Tabs land on "CAPTURE Box 4" in the page behind the drawer. The Mark down, Clear, Reconcile, Identify and Read-a-box sheets all move focus in and carry `aria-modal="true"`.
- Shot: ACC-04, screenshot not kept.
- Direction: the drawer acts like the app's other sheets. Focus moves in, stays in, and goes back to the button on close.
- Component: `app/src/App.tsx`, the phone drawer (`.bn-sheet.bn-sheet-left.bn-drawer`, "Screens").
- Annotation: no decision covers this. D95 (the shell is a rail, a palette and a reference sheet) builds the drawer and says nothing about focus. prior: none, shell.md put the drawer out of scope.

### ACC-05 The phone drawer hides Graveyard and Codes below its fold
- Severity: S2
- Screens: the shell, every owner screen
- Where: 390x844 (Graveyard and Codes hidden), 360x740 (Codes hidden), both themes
- Repro: open `#/` at 390x844 and tap Menu (or "More" in the tab bar).
- Seen: the nav list is 542 px tall over a 629 px scroll height. Under "Library" only "Inventory" shows, then a divider and "Cards to pull". Graveyard and Codes sit under the foot. The only sign is a 32 px fade. The Library group looks complete with one row, so two screens seem not to exist on a phone.
- Shot: ACC-05, screenshot not kept.
- Direction: every screen in the drawer shows without a scroll on a common phone. If not, the list shows plainly that it continues.
- Component: `app/src/App.tsx`, `nav.bn-nav` "All screens" in the drawer, and its foot (Cards to pull, theme, server status).
- Annotation: caused by D204 (the drawer scrolls above its foot). D204 proved that Codes is tappable after a scroll. It did not ask whether a person knows to scroll. The fade is the only cue. prior: none.

### ACC-06 Product history has no way in except a typed URL
- Severity: S2
- Screens: `#/product` (and every screen that names a product)
- Where: all
- Repro: open the command palette (Search at phone width, ⌘K at desk width) and type "product". Look for a link to `#/product` on `#/revenue`, `#/pricing` and `#/inventory`.
- Seen: the palette answers "Nothing matches "product"". No anchor on any screen points into `#/product`. The drawer and the sidebar do not list it. On a phone the only way to the screen is to type the URL.
- Shot: ACC-06, screenshot not kept.
- Direction: the owner reaches a product's history from where a product is named (a Sales row, a Pricing row) and from the palette.
- Component: `app/src/App.tsx`, the palette's go-to list (`ROUTES.filter((r) => r.nav)`) and the `#/product` row (no `nav`).
- Annotation: caused by D227 (a route, not a lens). D227 says off-nav, not off-limits, and names a bookmark, a note and an order line as ways in. The `ROUTES` comment deferred the Sales link, and nothing added it later. The palette's `nav` filter drops the route too. This also violates the hard rule that a route is not a feature until a screen reaches it. prior: none, product.md reached the screen by a deep link.

### ACC-07 Pricing worklist details read at 3:1
- Severity: S2
- Screens: `#/pricing`
- Where: 1440 and 390. Light 3.0:1, dark 3.33:1
- Repro: open `#/pricing` and read the grey line under each card name (condition, set, rarity, number) and the "On the rule" state.
- Seen: `#91959c` on `#ffffff` is 3.0:1 at 11-12 px (62 nodes at 390 light). In dark, `#646b75` on `#14171c` is 3.33:1. The "Market" label in the reference chip is 2.7:1 (light) and 3.58:1 (dark) at 10 px. These lines carry "Near Mint Foil" against "Near Mint", which decides the price. The price field's own text (`#72767d` on `#f1f3f6`) is 4.1:1.
- Shot: ACC-07, screenshot not kept.
- Direction: every fact that changes a price decision reads at 4.5:1 or better in both themes.
- Component: `app/src/Pricing.tsx`, `.pricing-meta` spans, `.pricing-cond`, `.pricing-state-quiet`, `.pricing-ref-label`, `.pricing-input`.
- Annotation: no decision covers this. prior: related, not the same. system.md logged `--bn-ink-3` at 4.43:1. These spans use a lighter ink than that.

### ACC-08 Sidebar hints and group labels fall under contrast
- Severity: S3
- Screens: every owner screen at desk width
- Where: 1440, light and dark
- Repro: open `#/runs` at 1440x900 and look at the sidebar.
- Seen: the ",H" and ",C" key hints are `#abaeb4` on white, 2.22:1 (dark 2.42:1), at 10 px. On the current row they are 2.39:1. The group labels "Workflow", "Sell" and "Library" are 10 px bold at 3.63:1 in light. "122 cards" in the server line is 3.63:1. These give about 15 of the axe contrast nodes on every route.
- Shot: ACC-08, screenshot not kept.
- Direction: the sidebar's labels and hints read at a glance. A hint that is worth drawing is worth 4.5:1.
- Component: `app/src/App.tsx`, `.bn-nav-group-label`, `kbd.bn-kbd` in the nav rows, `.bn-server-detail`.
- Annotation: no decision covers this. prior: system.md logged `.bn-menu-label` at ink-4 on 10 px text. The sidebar group labels repeat that pattern.

### ACC-09 The tab bar shows no location on eight screens
- Severity: S3
- Screens: `#/`, `#/runs`, `#/pricing`, `#/shipping`, `#/revenue`, `#/graveyard`, `#/codes`, `#/product`
- Where: 390 and 360, both themes
- Repro: open `#/shipping` at 390x844 and look at the bottom tab bar.
- Seen: the tab bar holds Capture, Review, Orders, Inventory and More. On the eight screens above no tab is lit, and "More" never shows a current state. The phone never tells the owner where they are. On `#/shipping`, "Orders" is not lit either, but Shipping is a stage of the Orders screen. The Menu and More buttons have no `aria-expanded` or `aria-haspopup`.
- Shot: ACC-09, screenshot not kept.
- Direction: every screen shows its place in the phone's bottom bar. The two buttons that open the drawer say that they open it.
- Component: `app/src/App.tsx`, `TabBar` (`nav.bn-tabbar`, the "More" `button.bn-tab-link`) and the top bar's Menu button.
- Annotation: caused by D95 (the shell is a rail, a palette and a reference sheet). D95 puts four routes on the bar and everything else behind the drawer. It gives the other eight screens no current state. D204 keeps the bar at five slots on the owner's word. prior: none.

### ACC-10 Keyboard hints show on a touch phone
- Severity: S3
- Screens: `#/`, `#/capture`, the palette
- Where: 390 and 360, both themes
- Repro: open `#/` at 390x844 with touch. Then open `#/capture`. Then tap Search.
- Seen: Home's "Cannot be filled" card carries a ",O" key chip. Capture's Box picker carries a "B" keycap, and "Capture card" carries a "C" keycap. The palette footer reads "↑↓ move", "↵ open" and ", + letter jumps anywhere". Its "esc" chip looks like a button but is a `<kbd>` that does nothing on a tap. A finger can use none of these.
- Shot: ACC-10, screenshot not kept.
- Direction: on a touch device the screen shows only what a finger can use.
- Component: `app/src/Home.tsx` standing card. `app/src/CaptureScreen.tsx` box row and shutter. `app/src/App.tsx` palette (`.bn-cmdk`) footer.
- Annotation: no decision covers this. D51 (Cmd-arrow steps the strip) and D95 own the keys, not how they show on touch. prior: home.md logged the `,O` chip at 1440 as a hint with no affordance. On a phone it has no use at all.

### ACC-11 Touch targets under 40 px
- Severity: S3
- Screens: `#/pricing`, `#/shipping`
- Where: 390 and 360, both themes (hit area probed with `elementFromPoint`)
- Repro: open `#/pricing` at 390x844. Scroll to "Ready to write" and to the "Above the cut-off" list. Then open `#/shipping`.
- Seen: the Pricing "Compare" toggle is 98x34 (two of them). The inline links "14 never identified" and "9 in review" are 16 px tall and about 8 px apart. Shipping's "What this file does not carry" disclosure is 18 px tall. All other owner controls on the non-held screens measured 40 px or more.
- Shot: ACC-11, screenshot not kept.
- Direction: every control a thumb presses meets the app's own 40 px floor. This includes links inside a sentence.
- Component: `app/src/Pricing.tsx` `button.pricing-compare-toggle` and the "Not on this list" line. `app/src/Shipping.tsx` `summary` "What this file does not carry".
- Annotation: violates D117 (the thumb floor is the kit's, the measurement is the hit area). D208 (one verdict on Pricing) added the Compare toggle. prior: none.

### ACC-12 Field and checkbox edges at 1.4:1
- Severity: S3
- Screens: `#/pricing`, `#/product`, `#/gallery` (held: `#/inventory`, `#/orders`)
- Where: 1440 and 390. Light 1.41:1, dark 1.56-1.63:1 (measured, partly seen)
- Repro: open `#/product` and look at the SKU field. Open `#/pricing` and look at the quantity fields and the "split in two" checkbox.
- Seen: `.bn-input`, `.bn-select` and plain checkboxes draw a 1 px edge at `rgba(15,18,23,0.16)`. The fill is the same as the surface, so the edge alone shows where to type. It is 1.41:1. The pricing price field (`.pricing-input`) and the search fields carry their own wrapper border.
- Shot: ACC-12, screenshot not kept.
- Direction: every field and checkbox edge reads at 3:1 against the surface in both themes.
- Component: `app/src/kit.css` `.bn-input`, `.bn-select`. `app/src/Pricing.tsx` `.pricing-qty-input`, `.pricing-ship-cap-input`.
- Annotation: violates D50 (an interactive element's feedback is the product's). D50 set the field edge `--field` at 3.36:1, the quietest edge that WCAG 1.4.11 permits. `--field` now reads `--bn-line-strong`, and `.bn-input` draws 1.41:1. prior: none. system.md called the input states complete but did not measure the rest edge.

### ACC-13 Pricing's price field focus ring is a faint halo
- Severity: S3
- Screens: `#/pricing`
- Where: 1440, light and dark
- Repro: open `#/pricing` at 1440 and Tab into a price field.
- Seen: the field's border stays grey (`#7f8791`). Focus adds only a 3 px halo at 18% alpha, about 1.3:1 against white. Search fields and `.bn-input` pass, because their border turns accent on focus. Every button, link and nav row shows a 2 px solid accent outline (30 Tab stops walked per route, none missing).
- Shot: ACC-13, screenshot not kept.
- Direction: a keyboard user sees which price field has focus as clearly as on every other control.
- Component: `app/src/Pricing.tsx`, the price cell wrapper around `input.pricing-input`.
- Annotation: violates D50 (an interactive element's feedback is the product's). D50 relies on the global focus ring in `base.css`. The price cell replaces it with a local halo. prior: none.

### ACC-14 Capture has no h1 on a phone
- Severity: S3
- Screens: `#/capture`
- Where: 390 and 360, both themes (measured, not seen)
- Repro: open `#/capture` at 390x844 and list the headings.
- Seen: the only h1 ("Capture") has zero height at phone width, so the screen has no heading at all. axe reports `page-has-heading-one`. Every other screen keeps its h1 on a phone.
- Shot: ACC-14, screenshot not kept.
- Direction: the capture screen names itself to a screen reader at every width.
- Component: `app/src/CaptureScreen.tsx`, the page head.
- Annotation: no decision covers this. D32 (the pixel budget is spent on the card) explains why the visible title goes at phone width. It does not require the heading to leave the page outline. prior: none, capture.md checked 1440 only.

### ACC-15 Capture puts an aria-label on a plain paragraph
- Severity: S3
- Screens: `#/capture`
- Where: all (axe `aria-prohibited-attr`, serious. Measured, not seen)
- Repro: open `#/capture` and run axe.
- Seen: `<p class="capture-odo-split" aria-label="Where this sitting went">`. Screen readers ignore a label on an element with no role, so the name is lost.
- Shot: ACC-15, screenshot not kept.
- Direction: the sitting summary is read out with its name, or the name is visible text.
- Component: `app/src/CaptureScreen.tsx`, `.capture-odo-split`.
- Annotation: no decision covers this. prior: none.

### ACC-16 Reduced motion speeds up the live dot and keeps the shimmer
- Severity: S3
- Screens: any screen that draws a live dot or a skeleton (the live dot was measured on `#/inventory`, skeletons on route loads such as `#/runs`)
- Where: 1440, `prefers-reduced-motion: reduce` (measured, not seen)
- Repro: emulate reduced motion, open `#/inventory` and list `document.getAnimations()`. Then go to `#/runs` and sample at 80 ms.
- Seen: with reduced motion on, transitions drop to 0.01 ms and the page-in slide is gone. The live dot's `bn-pulse` runs at 1.4 s per beat under reduce, faster than its normal 1.8 s. The skeleton `bn-shimmer` keeps its sweep (1.4 s, no end). Busy spinners keep turning more slowly, which is fair.
- Shot: ACC-16, screenshot not kept.
- Direction: a request for less motion never makes a thing move faster, and decorative sweeps stop.
- Component: `app/src/base.css`, the `@media (prefers-reduced-motion: reduce)` block and its list of loops that it keeps (`.bn-skeleton::after`, `.bn-dot-live`).
- Annotation: no decision covers this. The `base.css` comment argues that a stopped shimmer reads as broken content. That argument does not cover a dot that beats faster. prior: system.md called the reduced-motion block a strength. It did not measure the dot's rate.

### ACC-17 Mark down sheet hides its only forward action at the bottom of the scroll
- Severity: S3
- Screens: `#/pricing` (Mark down sheet)
- Where: 390 and 360, both themes
- Repro: open `#/pricing` at 390x844 and tap "Mark down".
- Seen: the sheet fits, scrolls and closes (Close, Escape). Its pinned footer holds only "Not now". The forward action "Fetch my live listings" sits at the end of a 1,044 px scroll body, below four form fields and a long note. The Clear sheet pins its primary action and Cancel together.
- Shot: ACC-17, screenshot not kept.
- Direction: on a phone, a sheet's forward action sits next to its dismiss action.
- Component: `app/src/Markdown.tsx`, the sheet footer.
- Annotation: no decision covers this. D105 (the markdown lives where prices are decided) places the sheet, not its footer. prior: none.

### ACC-18 Home's stage notes are cut short at 390
- Severity: S3
- Screens: `#/`
- Where: 390, both themes
- Repro: open `#/` at 390x844 and scroll to the stage tiles.
- Seen: "18 cards in Mixed Singl…" and "27 copies to pull and 6 not found" end in an ellipsis inside 141 px tiles. The part that is cut ("6 not found") is the part that needs action.
- Shot: ACC-18, screenshot not kept.
- Direction: a tile's sentence reads whole on a phone, or the tile gives a short form on purpose.
- Component: `app/src/Home.tsx`, `.home-stage-note`.
- Annotation: no decision covers this. D121 (the front page says what is owed) makes the owed part the point of Home. The ellipsis cuts exactly that part. prior: none, home.md checked 1440.

### ACC-19 Shipping is a 37,000 px page on a phone
- Severity: S3
- Screens: `#/shipping`
- Where: 390 (37,150 px) and 360 (37,465 px), both themes
- Repro: open `#/shipping` at 390x844 with a loaded export (the demo loads one).
- Seen: all 331 orders draw as cards in open lanes. The parcel lane and the "cannot tell" lane sit about 44 screens below the first. The lane header's chevron folds a lane, but the lanes start open.
- Shot: ACC-19, screenshot not kept.
- Direction: on a phone the owner sees every lane's count and goes to a lane in one screen.
- Component: `app/src/Shipping.tsx`, the lane sections.
- Annotation: no decision covers this. D61 (the shipping lane is three lanes) sets the lanes, not whether they start open. prior: none, shipping.md did not see the populated stage.

### ACC-20 Several screens have one heading and nothing to jump between
- Severity: S3
- Screens: `#/runs`, `#/shipping`, `#/codes`, `#/graveyard`, `#/product`, `#/capture` (desk)
- Where: all widths (measured, not seen)
- Repro: list `h1-h6` per route.
- Seen: these screens have only an h1. The "Runs" card title, the shipping lane names ("Envelope"), the export cards and the empty-state titles ("No codes on file yet") are not headings. Pricing, Sales, Kit and Cards to pull have a clean h1, h2, h3 outline with no skipped level. Every route has one `main`. The phone has a labelled `nav` ("Primary") and a `banner`.
- Shot: ACC-20, screenshot not kept.
- Direction: each visible section title is a heading, so a screen-reader user can go from section to section.
- Component: `app/src/Runs.tsx`, `app/src/Shipping.tsx`, `app/src/Codes.tsx`, and the kit's empty state (`app/src/kit/index.tsx`).
- Annotation: no decision covers this. prior: none.

### ACC-21 The kit fails axe and does not fit a phone
- Severity: S4
- Screens: `#/gallery`
- Where: all widths, both themes
- Repro: open `#/gallery` and run axe. At 390, scroll to the Data table.
- Seen: the kit's tab buttons carry `aria-selected="true"` with no `role="tab"` (axe critical `aria-allowed-attr`). Three field samples and one select sample have no label (axe critical `label`, `select-name`). The Data table is 402 px wide on a 390 px screen with no scroller, so its right column is cut. Index buttons sit 2 px apart. Its samples give 72-96 contrast nodes, most of them captions.
- Shot: ACC-21, screenshot not kept.
- Direction: the kit shows the accessible form of each primitive, because the kit is what the next screen copies.
- Component: `app/src/Gallery.tsx`, the `Tabs` sample (`.bn-tab`), and the Fields and Data samples.
- Annotation: no decision covers this. D117 moved `.bn-tab` into the kit for its height, not its role. prior: none. kit.md read the Data table as text only and did not see the cut.

### ACC-22 Sales table: an empty header and a wide empty column
- Severity: S4
- Screens: `#/revenue`
- Where: all widths (axe `empty-table-header`). Width seen at 390
- Repro: open `#/revenue` at 390x844 and look at the table's first column.
- Seen: the disclosure column's `<th>` is empty. On a phone the column with only a chevron takes about a quarter of the table width. The names lose that width in ACC-03.
- Shot: ACC-22, screenshot not kept.
- Direction: the disclosure column is as narrow as its chevron, and its header has a hidden name.
- Component: `app/src/Revenue.tsx`, `th.revenue-disclosure-col`.
- Annotation: no decision covers this. prior: none.

### ACC-23 Cards to pull cuts its own search hint
- Severity: S4
- Screens: `#/fulfillment`
- Where: 390 and 360, both themes
- Repro: open `#/fulfillment` at 390x844.
- Seen: the placeholder reads "For example, Piercing Li". The example card name is cut.
- Shot: ACC-23, screenshot not kept.
- Direction: the hint fits the field at phone width.
- Component: `app/src/Fulfillment.tsx`, the search field placeholder.
- Annotation: no decision covers this. `docs/DESIGN.md` sets this screen's 20 px body, which makes the hint long for the field. prior: none.

### ACC-24 Capture's Run panel leaves an empty column at 390
- Severity: S4
- Screens: `#/capture`
- Where: 390, both themes
- Repro: open `#/capture` at 390x844 and scroll just under the camera frame.
- Seen: the "RUN" panel (Box picker, Capture card) is about 290 px wide. It leaves about 70 px of empty space to its right, while the camera card above spans the full width.
- Shot: ACC-24, screenshot not kept.
- Direction: the phone column is one width.
- Component: `app/src/CaptureScreen.tsx`, the run block.
- Annotation: no decision covers this. prior: none.

### ACC-25 The translucent tab bar shows large text through its labels
- Severity: S4
- Screens: all owner screens
- Where: 390, both themes
- Repro: open `#/pricing` at 390x844 and stop with a large heading behind the tab bar.
- Seen: the bar is 72% opaque with a 14 px blur. Big headings behind it show as grey letter shapes between the 10 px labels ("PRIC", "ING TO ADD"). Small text blurs out cleanly.
- Shot: ACC-25, screenshot not kept.
- Direction: the bar's labels always sit on a quiet ground.
- Component: `app/src/App.tsx` `nav.bn-tabbar`, and `app/src/App.css`.
- Annotation: no decision covers this. D205 (the phone tab bar has one height) sets its height, not its opacity. prior: none.

### ACC-26 The palette has no close control on a phone
- Severity: S4
- Screens: the shell (palette)
- Where: 390 and 360
- Repro: open `#/` at 390x844, tap Search, and try to close it.
- Seen: the "esc" chip is not a button. A tap on the dim page closes the palette (this works), but nothing on the palette says so.
- Shot: ACC-26, screenshot not kept.
- Direction: the palette shows a Close control on touch devices, as the sheets do.
- Component: `app/src/App.tsx`, `.bn-cmdk`.
- Annotation: no decision covers this. D95 builds the palette. prior: none. shell.md opened the palette by a key event only, so touch was not checked.

## Measurements

Horizontal scroll, `scrollWidth - clientWidth`, light/dark. Held screens are in the table for the record.

| Route | 390x844 | 360x740 | Page height at 390 |
|---|---|---|---|
| `#/` | 0/0 | 0/0 | 1,638 |
| `#/capture` | 0/0 | 0/0 | 1,978 |
| `#/runs` | 0/0 | 0/0 | 844 |
| `#/review` | 0/0 | 0/0 | 1,365 |
| `#/pricing` | 0/0 | **6/6** | 9,676 |
| `#/orders` | 0/0 | 0/0 | 844 |
| `#/shipping` | 0/0 | 0/0 | 37,150 |
| `#/revenue` | 0/0 | 0/0 (the table's own scroller: 8 at 390, 38 at 360) | 2,624 |
| `#/inventory` | 0/0 | 0/0 | 1,499 |
| `#/graveyard` | 0/0 | 0/0 | 844 |
| `#/codes` | 0/0 | 0/0 | 844 |
| `#/fulfillment` | 0/0 | 0/0 | 1,008 |
| `#/gallery` | 0/0 (table cut, not scrolled) | 0/0 | 27,306 |
| `#/product` | 0/0 | 0/0 | 844 |

Hit areas under 40 px on non-held screens (probed): Pricing "Compare" 98x34 (two), "14 never
identified" 104x16, "9 in review" 62x16. Shipping summary 184x18. All others are 40 or more. The tab
bar's five cells are 78x63.

axe violations, non-held routes, summed across routes (nodes):

| Rule | Impact | 1440 light | 1440 dark | 390 light | 390 dark | Where |
|---|---|---|---|---|---|---|
| color-contrast | serious | 310 | 289 | 174 | 154 | Kit 72-96 and Pricing 71-88 per run. About 15 per route at 1440 from the sidebar (ACC-08). One per route at 390 from the brand wordmark, a logotype and exempt |
| aria-prohibited-attr | serious | 1 | 1 | 1 | 1 | Capture (ACC-15) |
| aria-allowed-attr | critical | 1 | 1 | 1 | 1 | Kit (ACC-21) |
| label | critical | 3 | 3 | 3 | 3 | Kit (ACC-21) |
| select-name | critical | 1 | 1 | 1 | 1 | Kit (ACC-21) |
| empty-table-header | minor | 1 | 1 | 1 | 1 | Sales (ACC-22) |
| page-has-heading-one | moderate | 0 | 0 | 1 | 1 | Capture (ACC-14) |

No route has a `button-name`, `link-name`, `image-alt` or `aria-dialog-name` violation. Every
icon-only control has a name (Reload, Search, Menu, Close, Collapse the sidebar, Card actions,
Price history for X, Hold X). Segmented controls use `aria-pressed` (Sales, Pricing). The Orders
and Shipping stage tabs use `role=tab` with `aria-selected`. Nav rows and tab-bar links use
`aria-current="page"`. Sales disclosures use `aria-expanded`. The gaps are the drawer buttons
(ACC-09) and the kit's tab sample (ACC-21).

Sheets on a phone (390 and 360): the Mark down, Clear, Reconcile, Identify and Read-a-box sheets
all fit the viewport and scroll inside their body. Each moves focus in, carries
`aria-modal="true"` and a labelled title, and closes by its Close button and by Escape. The drawer
(ACC-04) is the one dialog that does none of the focus work.

## Held-screen notes

Main state. Re-check after merge.

- `#/review` at 390: the reason filter chips measured 28 px tall on the first run and 40 px on the second. The chips after the second sit in a sideways scroller. Check the settled height. The "Next" label is 2.81:1 (`#666c76` on `#bcbdbe`, 10 px bold).
- `#/inventory` and `#/orders`: every row checkbox and the section tick draw a 1.41:1 edge in light and 1.63:1 in dark. This is the ACC-12 defect. The `.bn-select` filters are 1.41:1.
- `#/inventory` and `#/orders`: 33-34 contrast nodes at `#7f8791` on white, 11 px, 3.63:1 (dark 4.03:1). These are box identity and order ids in the rail.
- `#/orders` at 360: the last list item's bottom edge measured 758 px in a page whose height is 740 (measured, not seen). Check that it is reachable above the tab bar.
- `#/inventory`: the live dot is where the ACC-16 pulse was measured.
- `#/orders` and `#/shipping` stage tabs: 138x40 and 166x40, 4 px apart. The size is correct. The spacing is close.

## What I could not check

- A real phone: iOS Safari safe-area insets, the on-screen keyboard over a focused field, and pinch zoom. I used Chromium emulation only.
- Screen-reader speech. I checked the ARIA that a reader uses, not what VoiceOver or TalkBack says.
- 820 px for the accessibility pass (the brief asks for 1440 and 390). The drawer also serves 820, so ACC-04 probably holds there (unknown).
- Browser zoom to 200% and text-only zoom reflow.
- The Graveyard list, and each screen state that the demo refuses. I graded only the refusal state.
- Focus order after the first 30 Tab stops per route, and focus return after a sheet closes.
- The dark-theme drawer at 360, and the sheets on the held screens (Manage box, Review close).
