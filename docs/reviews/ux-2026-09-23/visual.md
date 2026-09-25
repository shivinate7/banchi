# Visual system

Lens 3. Target: the published demo (built from PR #454) at 1440x900, 820x900 and 390x844, light and dark, all 14 routes from `app/src/App.tsx` `ROUTES`. Also a read-only look at the owner's live app at 1440 (see "Live look" below).

Screenshots, probe scripts and raw data: not kept in this record.

Note on full-page shots: the sidebar ends at 900px and the Pricing ship bar floats mid-page in full-page shots. Both are sticky or fixed elements that a full-page capture draws once. They are capture artifacts, not findings.

## Grade matrix
| Route | Grade | One-line reason |
|---|---|---|
| `#/` Home | C | Display type is 2x any other title. Mono on a date and a box name. The spine note truncates at 1440 only. "Needs pricing" is two colors on one screen. |
| `#/capture` | B | Coherent. Keycaps sit left of labels here and right of labels in the sidebar. No visible title at 390. |
| `#/runs` | B | Clean, but very sparse at 1440. At real density, 7 of 17 runs sit in a hidden inner scroll. |
| `#/review` | HELD | Held screen. |
| `#/pricing` | F | At 1440 the "Lists at" field is 9px wide and shows `$1` for 13.11 and `$0` for 0.49. The owner reads the wrong price. |
| `#/orders` | HELD | Held screen. |
| `#/shipping` | C | Raw reason codes (`cards_only`, `value_at_threshold`, `no_weight_data`) in mono on every card. Most text is 11px. |
| `#/revenue` Sales | C | The one screen with no panels. The name cell's rule sits 14px above the row rule. The chart labels only its two ends. At real density: 562 rows on a 30,598px page. |
| `#/inventory` | HELD | Held screen. |
| `#/graveyard` | D | The demo cannot draw it. At real density (live) the table is 77px wider than the page, the Run column is cut off, and the page is 86,935px tall. |
| `#/codes` | B | Consistent empty state. Two competing "start" actions (header primary and empty-state secondary). |
| `#/fulfillment` | F | Its type system holds together, but its first sentence is false at real data: "No orders are waiting" while the store has 71 open orders (VIS-34). Pass 1 graded B on looks alone. I changed it after the coordinator's question and the live evidence, not from an annotation. |
| `#/gallery` Kit | B | Index labels and token names are 10px at 3.33:1 in light. |
| `#/product` | C | No screen links to it. The SKU field spans 1,140px for a 7-digit number. |

## Findings

### VIS-01 Pricing "Lists at" field shows the wrong price at 1440
- Severity: S1
- Screens: `#/pricing`
- Where: 1440/light and dark (the 8-column row grid). Correct at 820 and 390.
- Repro: open `https://shivinate7.github.io/banchi/#/pricing` at 1440x900. Look at the "Lists at" column.
- Seen: the field shows `$ 1` for a value of `13.11`, `$ 2` for `2.52`, and `$ 0` for `0.49`. Measured: `input.pricing-input` is 9px wide (clientWidth 9, scrollWidth 46 for "13.11"). The row grid is `36px 444px 56px 68px 68px 68px 132px 68px`. The price column gets 68px, and the margin, the `$` glyph, the gap, the padding and the check icon take all but 9px of it. The same data at 820 shows `13.11`. At the owner's desk width, the price reads as a whole-dollar figure that is wrong.
- Shot: VIS-01, screenshot not kept.
- Direction: the typed or suggested price must be fully legible at every width. Size the price column from its widest value, not from what is left over.
- Component: `app/src/Pricing.tsx` row `.pricing-price` > `label.pricing-field` > `input.pricing-input`. The grid is `.pricing-row` in `app/src/Pricing.css`.
- Annotation: no decision covers this. D208 (one verdict on Pricing) and D197 (one left edge, Pricing keeps its 1120px cap) shape the screen but not this column. Likely cause, measured but not confirmed: the row has 5 children (`pricing-facts` draws 0px wide) and the grid has 8 tracks, `36 444 56 68 68 68 132 68` under `data-trends=off`. The price lands in a 68px track while a 132px track sits beside it. The field rules date from 2026-09-04 (commit 379ce843). prior: not in ux-2026-09-20.

### VIS-02 Sales product names at real density are the full catalog string
- Severity: S2
- Screens: `#/revenue`
- Where: 1440/light and dark, live app.
- Repro: live app `#/revenue`, "By product" table. The demo's names are short card names and do not show it.
- Seen: every row reads as the full catalog string: game, set, card name, number and condition (live string not kept). The same 50-character prefix repeats on hundreds of rows. The card name, which is the thing a person scans for, sits in the middle of the string. The Copies, Gross and Last-sold columns get only the right 290px.
- Shot: VIS-02, screenshot not kept.
- Direction: lead each row with the card name. Show set, number and condition as quiet secondary text. Show the game once, not on every row.
- Component: `app/src/Revenue.tsx`, the name cell of the `.revenue-products` table.
- Annotation: caused by D214 (a gross-revenue retrospective, searchable by name). D214 measured 539 distinct product names on the real ledger and still draws each name verbatim. A decision that caused this outcome is an argument, not a defence. prior: not in ux-2026-09-20.

### VIS-03 Graveyard table is cut off on the right at real density
- Severity: S2
- Screens: `#/graveyard`
- Where: 1440/light and dark, live app.
- Repro: live app `#/graveyard` at 1440x900.
- Seen: the table's right edge is at x=1517 on a 1440 viewport. The Run column shows `2026-09-0…`, cut by the page edge. The Order column is 250px wide and holds only `–` on every visible row. The SKU cell wraps "Near Mint Foil" to three lines, so every row is 76px tall. 1,180 rows make an 86,935px page.
- Shot: VIS-03, screenshot not kept.
- Direction: fit the table to the page at 1440. Give width to the columns that carry data. Keep condition on one line. Keep a 1,000-row list short enough to scan (paging, a time window, or "show more").
- Component: `app/src/Graveyard.tsx`, `table.bn-table.graveyard-table`.
- Annotation: no decision covers the width or the length. D134 (a departed record is buried, and the graveyard is where the departed are read) set the screen and its `.bn-table`. prior: ux-2026-09-20/graveyard.md finding 5 logged the length (863 rows, no virtualization), now 1,180. The width overflow at 1440 was not logged.

### VIS-04 Money is drawn in three faces
- Severity: S3
- Screens: `#/pricing`, `#/shipping`, `#/revenue`, `#/gallery`, held `#/review`
- Where: all
- Repro: open each route at 1440 light and compare a dollar figure.
- Seen: measured with `getComputedStyle` on every `$n.nn` text node. Sales uses JetBrains Mono 13-14px/600 (`.bn-money`, 23 nodes). The Pricing Market column uses Inter 13px/600 (30 nodes), and the price field uses Inter 16px/700. Shipping chips use Inter 11px/600 (331 nodes). Review candidates use Manrope 18px/800. The Kit stat value uses Manrope 22px/800. The same kind of number looks different on each screen.
- Shot: VIS-04, screenshot not kept.
- Direction: pick one face for a dollar figure and use it on every screen, also inside inputs and chips.
- Component: `.bn-money` (kit) on Sales only. `app/src/Pricing.css` `.pricing-ref-market` and `.pricing-input`. `app/src/Shipping.css` `.shipping-figure`. `app/src/ReviewQueue.css` `.review-candidate-price`.
- Annotation: violates D221 (money stays mono). D221 rules that money takes mono through `.bn-money` and never through a hand-rolled declaration. Its premise is measured false: it says Pricing's worklist already agrees on the mono face, but the Pricing Market column is Inter 13px. prior: ux-2026-09-20/pricing.md finding 4 logged Pricing money as raw strings (format, not face).

### VIS-05 Mono is used for prose, names and counts
- Severity: S3
- Screens: `#/`, `#/pricing`, `#/gallery`, shell, held `#/review` and `#/inventory`
- Where: all
- Repro: `#/` at 1440. Look at the date line and the hero pill. Then `#/pricing` and its card eyebrows.
- Seen: measured JetBrains Mono on these strings. The Home date "Wednesday, September 23" (11px/500). The Home hero pill "Box 4 · Mixed Singles" (a box name, 12px/600, the name in accent blue). The Home box figures "42 / 28 / 34 / 18" (counts). The Pricing eyebrows "Store policy" and "Before you write". The Kit eyebrow "Design system". The sidebar "122 cards". The mono face stops meaning "machine string" when a date, a box name and a heading label use it too.
- Shot: VIS-05, screenshot not kept.
- Direction: keep mono for SKUs, run ids, card numbers, key caps and money. Draw dates, names, counts and eyebrows in the UI face.
- Component: `app/src/Home.tsx` date line and hero pill. `app/src/Pricing.tsx` card eyebrows. `app/src/App.tsx` server detail.
- Annotation: no decision covers this. D221 (money stays mono) keeps mono for money and machine strings only, and these strings are neither. The type-role rule is marked NOT MECHANIZED in CLAUDE.md. prior: not in ux-2026-09-20.

### VIS-06 Shipping cards print raw reason codes
- Severity: S3
- Screens: `#/shipping`
- Where: all
- Repro: `#/shipping` at 1440. Look at the right end of each order card.
- Seen: every card ends with a mono code: `cards_only`, `value_at_threshold`, `no_weight_data` (331 nodes at 11px mono). The sentence on the same card already says it in words ("Cards only, and under $50."). The code adds a second, machine-shaped label to every card.
- Shot: VIS-06, screenshot not kept.
- Direction: remove the code from the card, or show it only where a person asks why.
- Component: `app/src/Shipping.tsx` lane card.
- Annotation: no decision covers it directly. D196 (no mechanism on screen) is the nearest, but its word list does not name enum codes. The 2026-09-20 review removed the same kind of code from Review on the owner's word (ux-2026-09-20/TASTE-CALLS.md, "The reason code: chip, tooltip, gone"). Shipping kept its copy. prior: not in ux-2026-09-20 for Shipping.

### VIS-07 Body text is 11-12px on the dense screens
- Severity: S3
- Screens: `#/pricing`, `#/shipping`, `#/revenue`, `#/runs`, held `#/inventory`
- Where: all widths
- Repro: run VIS-07 scratch file, not kept on each route.
- Seen: measured text-node counts by size at 1440. Shipping: 11px 1,193, 13px 340, 14px 1. Pricing: 12px 271, 13px 130, 11px 59, 14px 42. Inventory: 11px 67, 13px 31. The stated body size is 14px. On the working screens most text is 11-12px. Row metadata (condition, set, card number) is 11px on Pricing.
- Shot: VIS-07, screenshot not kept.
- Direction: set a floor for text a person must read (13px or more). Keep 10-11px for labels only.
- Component: tokens `--bn-fs-2xs` (10px) and `--bn-fs-xs` (11px) in `app/src/tokens.css`, used across screen CSS.
- Annotation: no decision covers a reading-size floor on owner screens. D117 (the thumb floor) sets a target floor, not a text floor. prior: ux-2026-09-20/system.md counted token use (`sm` 217, `xs` 163, `base` 54) but did not grade it as a defect.

### VIS-08 Sales is the one screen without panels
- Severity: S3
- Screens: `#/revenue`
- Where: all
- Repro: open the 1440 contact sheet. Compare Sales with its neighbours.
- Seen: every other owner screen puts its sections on white (light) or raised (dark) cards with a border and a radius. Sales puts the headline, the chart, the month list and the product table straight on the page ground, with hairlines between them. Its section headings are 11px/600 Manrope eyebrows ("BY MONTH", "BY PRODUCT"). Other screens use 16-18px headings with an icon. It reads as a different product.
- Shot: VIS-08, screenshot not kept.
- Direction: give Sales the same section surface and heading pattern as the other screens.
- Component: `app/src/Revenue.tsx`, `app/src/Revenue.css`.
- Annotation: no decision covers the surface. D214 and D217 (Sales becomes a tool) set the content, not the surface. prior: not in ux-2026-09-20.

### VIS-09 Sales product table: the name cell's rule floats above the row rule
- Severity: S3
- Screens: `#/revenue`
- Where: all widths, both themes, demo and live
- Repro: `#/revenue` at 1440 or 820, "By product" table.
- Seen: measured: each row's cells are 53px tall, but the Name `<td>` is 39px tall. Its bottom border sits 14px above the rest of the row's rule, and stops at the column edge. Every row shows a stepped double line.
- Shot: VIS-09, screenshot not kept.
- Direction: one continuous rule per row.
- Component: `app/src/Revenue.tsx` product table, the second `<td>` (name cell) in `.revenue-products tbody tr`.
- Annotation: no decision covers this. prior: not in ux-2026-09-20 (its sales.md finding 1 was the month-strip alignment, a different row).

### VIS-10 Sales chart labels only its two ends
- Severity: S3
- Screens: `#/revenue`
- Where: all. The live app with 6 months shows it best.
- Repro: `#/revenue`, "By month".
- Seen: a single 60px-tall line with no value axis, no point markers, and labels for the first and last month only. With 5 points (live) no point can be matched to its month or amount without the list below. The chart gives no reading that the list does not give.
- Shot: VIS-10, screenshot not kept.
- Direction: mark each month on the chart, or remove the chart and let the month list carry it.
- Component: `app/src/Revenue.tsx` by-month chart.
- Annotation: caused by D217 (Sales becomes a tool). D217 keeps the sparkline `aria-hidden` and puts the reading in the month strip, so the chart is decoration by design. The outcome is a chart that tells the owner nothing. prior: not in ux-2026-09-20.

### VIS-11 Sales at real density is a 30,598px page
- Severity: S3
- Screens: `#/revenue`
- Where: 1440, live app.
- Repro: live `#/revenue`. Scroll to the end.
- Seen: 562 product rows on one page, 30,598px tall. The "On the shelf" section and its "Value my stock" control sit at the very bottom, after all 562 rows.
- Shot: VIS-11, screenshot not kept.
- Direction: cap the product list (top N with "show all", or paging) so that the sections below it are reachable.
- Component: `app/src/Revenue.tsx`.
- Annotation: caused by D250 (unsold stock reaches `#/revenue`). D250 put "On the shelf" after the product table and says it was measured on an empty store. It did not see the table at 562 rows. prior: not in ux-2026-09-20.

### VIS-12 "Needs pricing" is two colors on one screen
- Severity: S3
- Screens: `#/`, `#/runs`
- Where: all
- Repro: `#/` at 1440 light. Compare the Pricing spine tile with "Recent runs".
- Seen: the Pricing tile's icon (and Review's and Orders') has an amber or orange tint for "attention". The same state in "Recent runs" is a blue accent pill "Needs pricing" (`bn-pill-accent`, rgb(61,90,241)). Blue also marks neutral counts ("7 open", "331 orders", "ongoing"). Green marks "open" on a box state, "Sold" and "Saved". One state has two colors, and one color has several states.
- Shot: VIS-12, screenshot not kept.
- Direction: give "needs the owner's action" one tone everywhere, apart from neutral counts.
- Component: `app/src/Home.tsx` stage tiles and recent runs. `bn-pill-accent` in `app/src/Runs.tsx`.
- Annotation: no decision covers a status-color map. prior: not in ux-2026-09-20.

### VIS-13 Heading scale has no steps
- Severity: S3
- Screens: all
- Where: 1440
- Repro: run VIS-13 scratch file, not kept. Read the `h` list.
- Seen: measured h1: 28px/800 on 11 screens, 56px/800 on Home, 38px on Cards to pull. Measured h2: 11px/600 (Sales), 16px/700 (Kit, Pricing cards), 16px/800 (Inventory, Orders), 18px/700 (Pricing), 22px/800 (Review, Inventory), 24px/800 (Cards to pull). Measured h3: 12px Inter/600 (Pricing groups) and 16px Manrope/700. Home's 56px is not on the token scale (the largest token is 48px). One heading level has six sizes.
- Shot: VIS-13, screenshot not kept.
- Direction: define three heading steps and map every h1, h2 and h3 to them.
- Component: per-screen CSS. Tokens `--bn-fs-*` in `app/src/tokens.css`.
- Annotation: no decision covers a heading scale. prior: ux-2026-09-20/system.md ("Type scale": "an accumulation, not a scale", about 20 rendered sizes) and ux-2026-09-20/kit.md finding 1. Still open.

### VIS-14 The title moves up and down between screens
- Severity: S4
- Screens: all owner screens
- Where: 1440
- Repro: switch screens from the sidebar and watch the title.
- Seen: measured h1 top: 16px (Review, page padding 16px), 24px (8 screens), 27px (Capture, padding 12px), 43px (Kit, eyebrow above), 53px (Home, date above). The left edge is the same everywhere (x=268). The vertical start is not.
- Shot: VIS-14, screenshot not kept.
- Direction: one top inset for every screen's title.
- Component: `.bn-page` padding overrides in `app/src/CaptureScreen.css` and `app/src/ReviewQueue.css`.
- Annotation: D197 (one left edge, only width may vary) protects the left edge only. No decision covers the top inset. prior: not in ux-2026-09-20.

### VIS-15 Page width has three maximums
- Severity: S4
- Screens: `#/pricing` (1120), `#/`, `#/codes`, `#/shipping` (1344), the rest (1600)
- Where: 1440 for Pricing. Wider desks for the rest (measured, not seen above 1440).
- Repro: `#/pricing` then `#/runs` at 1440. Compare the right edge.
- Seen: measured `.bn-page` max-width: 1120px on Pricing, 1344px on Home, Codes and Shipping, 1600px elsewhere. At 1440 Pricing's right edge stops 84px short of every other screen. On a desk wider than 1600, the three groups stop at three different right edges.
- Shot: VIS-15, screenshot not kept.
- Direction: fewer page widths, each chosen for a reason the screen shows.
- Component: per-route `.bn-page` max-width.
- Annotation: caused by D197 (one left edge, only width may vary). D197 argues that a pricing table and a three-column screen "legitimately want different caps". The outcome is a right edge that moves between screens. prior: not in ux-2026-09-20.

### VIS-16 Radii drift off the scale
- Severity: S4
- Screens: all
- Where: 1440
- Repro: run VIS-16 scratch file, not kept. Read `radii`.
- Seen: measured border-radius values in use: 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20, 22px and 50%. The token scale is 4, 6, 12, 16, 18 and 22px. The values 2, 3, 5, 7, 10, 14 and 20px are off the scale. 5px is on pills and chips on 12 screens.
- Shot: VIS-16, screenshot not kept.
- Direction: snap each radius to a token.
- Component: screen CSS files.
- Annotation: no decision covers radius drift. prior: ux-2026-09-20/system.md ("Radii, borders, shadows") and ux-2026-09-20/RANKING.md. The 18px step was named since (`--bn-r-2xl-sm`, per TASTE-CALLS.md). The 2, 3, 5, 7, 10, 14 and 20px values are still open.

### VIS-17 Tertiary text fails contrast in light
- Severity: S3
- Screens: `#/`, `#/revenue`, `#/gallery`, held `#/inventory` and `#/orders`
- Where: light. Dark measures 4.04-4.44:1.
- Repro: run VIS-17 scratch file, not kept at 1440 light.
- Seen: measured 3.33:1 for `--bn-ink-4` text on the page ground. Examples: Home "Behind that:" (13px), the Sales chart month labels (11px), the Kit index labels and token names (10px). Small pills: ok-green "Saved" 4.05:1 at 11px, warn "Short" 3.84:1 at 10px, accent `bn-pill-sm` 4.28:1 at 10px. All are under 4.5:1 for text this small.
- Shot: VIS-17, screenshot not kept.
- Direction: raise the lightest ink and the tinted pill inks to 4.5:1 in light, or keep them off text a person must read.
- Component: `--bn-ink-4`, `--bn-ok`, `--bn-warn` and `--bn-accent` on tints in `app/src/tokens.css`. `.bn-pill-sm` in `app/src/kit.css`.
- Annotation: no decision covers owner-screen contrast. docs/DESIGN.md's 7:1 floor applies to the Fulfiller's screen only. prior: ux-2026-09-20/RANKING.md item 2 and ux-2026-09-20/graveyard.md finding 3. The fix lane raised `--bn-ink-3` (FOLLOW-UPS.md). `--bn-ink-4` is still 3.33:1 in light.

### VIS-18 Pricing's ship bar covers a third of a phone
- Severity: S2
- Screens: `#/pricing`
- Where: 390/light and dark
- Repro: `#/pricing` at 390x844, no scroll.
- Seen: the sticky bar ("split in two", "hold to ... live", "Write the import file") is 186px tall (y 598-784), above a 60px tab bar. Together they cover 246 of 844px (29%) at every scroll position of the worklist.
- Shot: VIS-18, screenshot not kept.
- Direction: on a phone, pin only the write action. Move the two options into the flow or behind the action.
- Component: `app/src/Pricing.tsx` ship bar (`--pricing-ship-h`).
- Annotation: no decision covers it. D99 (one press writes one spreadsheet) put the write on this bar. prior: not in ux-2026-09-20, which was desktop only.

### VIS-19 Home spine note truncates at the widest width only
- Severity: S3
- Screens: `#/`
- Where: 1440 light and dark. The full text shows at 820.
- Repro: `#/` at 1440. Read the Orders tile.
- Seen: "27 copies to pull and 6 ..." is cut at 1440 (six tiles in one row). It shows whole at 820 (three tiles per row). The desk width, where the owner works, gets the worse version.
- Shot: VIS-19, screenshot not kept.
- Direction: the note must fit at 1440, or be shorter.
- Component: `app/src/Home.tsx` `.home-stage-note`.
- Annotation: no decision covers it. D121 (the front page says what is owed) owns the spine. prior: not in ux-2026-09-20 (its home.md checked 1280 and found the tiles consistent).

### VIS-20 Keycaps sit on different sides of their labels
- Severity: S4
- Screens: `#/capture`, shell, `#/`, `#/pricing`
- Where: 1440, 820
- Repro: `#/capture` at 1440. Compare the Stack and Rig rows with the sidebar.
- Seen: in Capture the key cap (H, R, F, G, V, O, T) sits left of the label. In the sidebar it sits right (`,H`). On Home's primary button it sits right, inside the button. On Pricing it sits beside the header ("M" next to "MARKET", "R" beside refresh). One idea has four placements.
- Shot: VIS-20, screenshot not kept.
- Direction: one placement rule for a shortcut hint.
- Component: `bn-kbd` in `app/src/CaptureScreen.tsx`, `app/src/App.tsx` and `app/src/Pricing.tsx`.
- Annotation: no decision covers placement. prior: ux-2026-09-20/capture.md finding 3 checked the Capture caps against each other and found them consistent. It did not compare them with the shell.

### VIS-21 Sidebar foot rows are misaligned
- Severity: S4
- Screens: shell (all owner screens)
- Where: 1440
- Repro: any owner screen at 1440. Look at "Cards to pull", "Search" and "Dark mode".
- Seen: measured: nav rows have an 18px icon at x=24 and a 36px row. "Search" and "Dark mode" have a 16px icon at x=29 and a 34px row. The two foot icons sit 5px right of every icon above them.
- Shot: VIS-21, screenshot not kept.
- Direction: one icon column and one row height for the whole sidebar.
- Component: `app/src/App.tsx` sidebar foot.
- Annotation: D152 (every row in the collapsed rail draws one glyph on one spine) guards the collapsed foot only. The expanded foot drifts 5px. prior: not in ux-2026-09-20.

### VIS-22 The CSS separator dot is glued to the next figure
- Severity: S4
- Screens: `#/pricing`
- Where: all widths
- Repro: `#/pricing`. Read the header meta and the "Ready to write" card.
- Seen: "22 of 22 decided ·8 nothing to add", "1 run ·1 box", "14 never identified ·9 in review". The dot has space before it and none after. Source: 68 hand-written `content: '·'` rules across 21 CSS files, with at least five margin patterns (`0 4px`, `0 6px`, `margin-left` only, `margin-right` only, `var(--bn-2)`).
- Shot: VIS-22, screenshot not kept.
- Direction: one separator primitive in the kit, used everywhere.
- Component: `app/src/Pricing.css` `::after` rules on `.pricing-scope`, `.pricing-machine` and `.pricing-meta`.
- Annotation: caused by D41 (the separator is deleted rather than replaced) and D218 (a typed dot is a defect). D218 moved each seam into CSS, file by file. It names five sibling rules but gives no kit primitive. So each file picks its own margins. prior: not in ux-2026-09-20.

### VIS-23 The Pricing toolbar wraps into ragged rows at 820 and 390
- Severity: S4
- Screens: `#/pricing`
- Where: 820 and 390
- Repro: `#/pricing` at 820.
- Seen: at 820 the refresh button and its `R` cap drop alone onto a second row. At 390 the toolbar is two rows of buttons with unequal widths, and "Runs 1" floats in the middle of the second row.
- Shot: VIS-23, screenshot not kept.
- Direction: a toolbar that folds as a unit (an overflow menu, or a fixed two-row grid).
- Component: `app/src/Pricing.tsx` toolbar.
- Annotation: no decision covers it. D195 (same-role stacked buttons share a width) exempts a horizontal row. prior: not in ux-2026-09-20.

### VIS-24 Sales period picker breaks into two rows on a phone
- Severity: S4
- Screens: `#/revenue`
- Where: 390
- Repro: `#/revenue` at 390x844.
- Seen: the five-segment control wraps to "3 months / 6 months / This year" over "All time / Custom", inside one grey tray. It no longer reads as one segmented choice.
- Shot: VIS-24, screenshot not kept.
- Direction: fit it in one row (shorter labels or a scrolling row), or use a select.
- Component: `app/src/Revenue.tsx` period control.
- Annotation: no decision covers it. prior: not in ux-2026-09-20.

### VIS-25 Cards to pull search placeholder is cut off on a phone
- Severity: S3
- Screens: `#/fulfillment`
- Where: 390 light and dark
- Repro: `#/fulfillment` at 390x844.
- Seen: the placeholder reads "For example, Piercing Li". This is the Fulfiller's one field, at 22px.
- Shot: VIS-25, screenshot not kept.
- Direction: a placeholder that fits the field at 390.
- Component: `app/src/Fulfillment.tsx` search field.
- Annotation: no decision covers it. docs/DESIGN.md's Fulfillment floors (20px body, 44px targets) are met, and none of them reads the placeholder. prior: not in ux-2026-09-20.

### VIS-26 The card count differs between the shell and the screens
- Severity: S3
- Screens: shell, `#/`, `#/fulfillment`, held `#/inventory`
- Where: all
- Repro: demo: read the sidebar foot, then Home's line, then Cards to pull. Live: the same.
- Seen: demo: sidebar "122 cards", Home "100 on hand in 4 boxes", Cards to pull "101 cards are in 4 boxes", Inventory "122 cards 4 boxes". Live: sidebar "3,510 cards", Cards to pull "2,633 cards are in 5 boxes". The same noun has different numbers, and nothing says what each one counts.
- Shot: VIS-26, screenshot not kept.
- Direction: one count per noun, or a word that tells them apart ("records", "on hand").
- Component: `app/src/App.tsx` server detail, `app/src/Home.tsx`, `app/src/Fulfillment.tsx`.
- Annotation: no decision covers it. prior: not in ux-2026-09-20 (its shell.md finding 6 read the server indicator, not the count).

### VIS-27 Runs list hides most of a real list without a cue
- Severity: S3
- Screens: `#/runs`
- Where: 1440, live app.
- Repro: live `#/runs` at 1440.
- Seen: the header says "17 runs". The card draws 10 and ends with a rounded foot. The full-page capture is 1,068px, so the other 7 must be in an inner scroll with no visible scrollbar and no fade. Measured, cause not confirmed: I did not scroll inside it.
- Shot: VIS-27, screenshot not kept.
- Direction: show that the list continues (a fade, a count of hidden rows, or no inner scroll).
- Component: `app/src/Runs.tsx` run list.
- Annotation: no decision covers it. prior: not in ux-2026-09-20.

### VIS-28 Runs is mostly empty space at 1440
- Severity: S4
- Screens: `#/runs`
- Where: 1440, both themes
- Repro: `#/runs` at 1440.
- Seen: a 320px list at the left, and an 800x360px panel that says only "Pick a run". Below 512px the page is empty. The first item on the screen is a small accent pill ("Every card waiting to be identified") beside the buttons.
- Shot: VIS-28, screenshot not kept.
- Direction: at desk width, open the newest run by default, or let the list use the width.
- Component: `app/src/Runs.tsx`.
- Annotation: D39 (the pipeline gets a route, and the selection is handed to it) created the layout. No decision covers the empty state at desk width. prior: not in ux-2026-09-20.

### VIS-29 Product history: the SKU field is page-wide
- Severity: S4
- Screens: `#/product`
- Where: 1440, 820
- Repro: `#/product` at 1440.
- Seen: the SKU input is 1,140px wide for a 6-7 digit number, with an 11px label. Search fields on Sales and Graveyard are 240-320px. No screen links to the route. A source search found only the route's own `#/product?sku=` builder.
- Shot: VIS-29, screenshot not kept.
- Direction: size the field to its content, like the other search fields. Link to it from the places that show a SKU.
- Component: `app/src/ProductHistory.tsx`.
- Annotation: caused by D227 (a route, not a lens). `App.tsx` records that D227 added no link from Sales because another branch held `Revenue.tsx`. That reason has expired. prior: not in ux-2026-09-20 (its product.md findings are about the range panels).

### VIS-30 Home display type is double every other title
- Severity: S4
- Screens: `#/`
- Where: all widths (56px at 1440 and 820, 36px at 390)
- Repro: switch from Home to any other screen.
- Seen: measured Home h1 56px/800. The other 11 screens use 28px. The greeting ("Good afternoon.") is the largest thing in the product and carries no information. The first useful item, the "Cannot be filled" line, comes second.
- Shot: VIS-30, screenshot not kept.
- Direction: let the owed line lead, at the product's title size.
- Component: `app/src/Home.tsx` greeting.
- Annotation: no decision covers the greeting's size. D121 (the front page says what is owed) argues the owed line leads, and the greeting outranks it. prior: ux-2026-09-20/system.md lists the 56px literal as off the token scale.

### VIS-31 Capture has no visible title on a phone
- Severity: S4
- Screens: `#/capture`
- Where: 390
- Repro: `#/capture` at 390x844.
- Seen: measured: the h1 is present but 0x0 at 390. Every other owner screen shows a 28px title at y=68. Capture starts with the counter strip.
- Shot: VIS-31, screenshot not kept.
- Direction: either every screen hides its title on a phone, or none do.
- Component: `app/src/CaptureScreen.tsx` header.
- Annotation: no decision covers it. prior: not in ux-2026-09-20, which was desktop only.

### VIS-32 Counts are drawn two ways
- Severity: S4
- Screens: `#/graveyard`, `#/pricing`, `#/shipping`, held `#/orders`
- Where: all
- Repro: compare Graveyard's filter tabs with Pricing's section heads.
- Seen: Graveyard tabs use parentheses, "All (1179)". Pricing ("15 SKUs"), Shipping ("331 orders") and Orders ("7 open") use a pill.
- Shot: VIS-32, screenshot not kept.
- Direction: one count style.
- Component: `app/src/Graveyard.tsx` filter tabs.
- Annotation: no decision covers it. prior: not in ux-2026-09-20 (its graveyard.md finding 6 is about the counts' sum, not their style).

### VIS-33 Codes offers two "start" actions
- Severity: S4
- Screens: `#/codes`
- Where: all
- Repro: `#/codes`.
- Seen: a filled primary "Read a box" in the header, and a secondary "Go to capture" in the empty state. On a feature the owner has not used, the page asks for two different first steps.
- Shot: VIS-33, screenshot not kept.
- Direction: one first step.
- Component: `app/src/Codes.tsx`.
- Annotation: no decision covers it. The feature is dormant (CLAUDE.md, 2026-09-20). prior: ux-2026-09-20/codes.md noted both controls and found no defect.

### VIS-34 Cards to pull says no orders wait while open orders owe copies
- Severity: S1
- Screens: `#/fulfillment` (compared with `#/`)
- Where: all widths and themes. Demo and live app. Live figures are
- Repro: demo: open `#/`, then `#/fulfillment`. Live: open `#/fulfillment`.
- Seen: demo Home says "6 copies for 7 open orders cannot be found" and "27 copies to pull". Demo Cards to pull says "No orders are waiting for a card right now." Live Cards to pull says the same sentence. The live `GET /orders` response that this screen reads on mount lists 71 open orders with 129 open lines and 216 copies wanted. The Fulfiller is told there is nothing to pull.
- Shot: VIS-34, screenshot not kept.
- Direction: Cards to pull must list every open order that owes a copy, or say how many it cannot place. It must never say "nothing is waiting" while orders are open.
- Component: `app/src/Fulfillment.tsx` `orderGroups` and the `waiting` memo. Likely cause, from the source and the wire counts: `orderGroups` builds cards only from `resolution.orders[].lines[].picks`, and `waiting` keeps only groups with at least one card. `GET /orders` carried 0 picks on both the demo (7 open orders, 29 copies wanted, 2 recorded) and the live app (71 open, 216 wanted, 0 recorded). The owner's Orders screen gets its picks from `POST /orders/picks` instead.
- Annotation: D212 (every copy is fungible, so no order claims one) measured `GET /orders` offering 84 picks on a seeded store. The wire now carries 0 picks on the demo and on the live app, and the owner's screen reads picks from `POST /orders/picks`. Cards to pull still reads them from `GET /orders`. Which change moved the picks is unmeasured. prior: not in ux-2026-09-20.

## Coordinator question: does live Cards to pull show orders when Home says copies are owed?

No. Live `#/fulfillment` shows "No orders are waiting for a card right now." The `GET /orders` response that the same page loaded lists 71 open orders, 129 open lines and 216 copies wanted (0 recorded). Home's own live figure is unknown: Home sends `POST /pipeline/crop-preview` on mount, so I did not load it. On the demo, Home says 27 copies to pull and 6 not found on 7 open orders, and Cards to pull says none wait.

## Live look (owner's app, 1440 only)

The live screenshots held real store data. They were not kept.

- Mount check, done before any load. I patched the demo's one request seam (`demoRequest`) in flight, on the demo only, to log each call a route makes on mount. I also read each view's mount effects in `app/src/`.
- Mount calls by route: Sales `GET /status, /orders`. Runs `GET /pipeline/runs, GET /pipeline/submissions, /boxes, /status`. Graveyard `GET /graveyard, /status`. Codes `GET /codes, /boxes, /status, /codes/lots`. Cards to pull `GET /inventory, /orders`.
- Source check. Sales' `getHoldingsValue` runs only after "Value my stock" is pressed (`holdingsOpened`). Runs' `cropPreview` runs only with the composer open. Codes' `scanCodes` and Cards to pull's `markSold` and `pullCopy` are in handlers only.
- Loaded: 9 page loads, one context, one page, in sequence. Sales, Runs, Graveyard, Cards to pull and Codes in light, then Sales, Runs, Graveyard and Cards to pull in dark. Each load took 704-1,071 ms. Playwright saw zero requests other than GET, HEAD or OPTIONS. I pressed, typed and submitted nothing.
- A tenth load, for the coordinator's question: `#/fulfillment` in light, in a new single context, 2,537 ms. I read the `GET /orders` response that the page made on mount and printed counts only. I stored no body. Zero write requests. Total: 10 loads of the 20 allowed.
- Skipped, with the reason:
  - `#/` Home: sends `POST /pipeline/crop-preview` on mount.
  - `#/pricing`: sends `POST /pipeline/crop-preview` on mount.
  - `#/shipping`: sends `POST /shipping/batches` and `POST /inventory/copies` on mount.
  - `#/orders`: sends `POST /orders/walk-plan`, `POST /orders/picks` and `POST /inventory/copies` on mount. Also HELD.
  - `#/inventory`, `#/review`: HELD. Mount calls are GET only, but no grade is permitted, so I kept the load budget.
  - `#/capture`: GET only, but no density question applies, and it drives the camera.
  - `#/gallery`, `#/product`: no store data to see without a SKU.
- The answer to the question (which layouts break at real density):
  - Sales' product table: full catalog names, 562 rows, a 30,598px page, and "On the shelf" at the end (VIS-02, VIS-11).
  - The Sales chart (VIS-10).
  - Graveyard: width overflow, a cut Run column, 3-line rows, 86,935px (VIS-03).
  - The Runs list: a hidden inner scroll (VIS-27).
  - The layouts of Cards to pull and Codes held up at real density. The Cards to pull message did not (VIS-34). Large numbers (two five-figure dollar totals, "2,633 cards") fit everywhere I looked.

## Held-screen notes

Main state, re-check after merge.

- `#/inventory`: the missing-photo state prints a raw URL in mono (`/banchi/demo/photos/1/1.jpg?card=demo-1-0001`). The rail pill "122 cards · 4 boxes" is mono. Box-number chips are black-filled on Home and white on Cards to pull. (Demo, 1440 and 390.)
- `#/orders`: raw enum codes in mono in the "why each line answered" legend: `no_copies_on_hand`, `sku_unknown`, `sku_unseen`, `not_a_single`. Order-id text is 11px at 3.64:1 in light. The `bn-pill-sm` "Short" is 3.84:1 at 10px.
- `#/review`: the card name "Draven, Audacious" is drawn in JetBrains Mono 12.6px/600. The position strip "BOX / SECTION / CARD" measured 2.80:1 in light. Candidate prices are Manrope 18px/800, a third money face (VIS-04).

## What I could not check

- `#/graveyard` on the demo: the demo has no recording for `/graveyard`, so the screen draws its failure state. I graded it from the live look only.
- `#/product` with data: the demo has no recording for a product history. I did not load it live, because it needs a SKU, and a SKU is store data. The loaded state is unknown.
- Widths above 1440: the three page maximums (VIS-15) are measured from CSS, not seen.
- Hover, focus and pressed states: not in this pass. Unknown.
- The live screens I skipped (Home, Pricing, Shipping, Orders, Inventory, Review, Capture) at real density: unknown. Pricing is the likeliest to show more, given VIS-01.
- The light-theme contrast figures for Capture's camera lamps (1.03-2.25:1) are probably false. The stage ground is a background image, which my probe cannot read. I left them out.
