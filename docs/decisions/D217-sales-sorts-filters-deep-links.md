## D217 — Sales sorts, filters, deep-links

**Problem.** D214 built `#/revenue` as a retrospective: a verdict, a month strip, and a product table sorted by gross. The owner's complaint: it was a list of items sold, with no way to work it. The table had one sort order. The month strip drew a sparkline with `aria-hidden`, and its rows had no handler, so a click did nothing. Nothing lived in the URL, so a view could not be shared or reloaded. A product's orders were unreachable. `Sale.order` carried them until dedupe folded them into `orderCount`.

**Nothing about what counts as revenue changed.** D214's rulings stand: gross only, canceled dropped silently, sealed and singles mixed on one list, and no buyer detail. This entry covers what a person can do with the same rows once they are on screen.

### Sortable columns

Name, Copies, Gross and Last sold each get a `<button>` inside their `<th>`. `aria-sort` is set on the active column, `ascending` or `descending`, and left off the rest. That is the ARIA APG shape. A first press picks the direction a reader wants first. Name sorts ascending. Everything else sorts descending: biggest gross, most copies, most recent sale. A second press on the same column flips the direction. Gross-descending stays the default, as D214 set it.

### The URL holds the one copy of the state, and it replaces rather than pushes

Period, search text, sort column and sort direction live in `#/revenue`'s query string. So do the active month or week filter, and a custom range's two dates. `readUrlState` reads the query once at mount. `writeUrlState` writes it on every change. This is D103's mechanism (`?band=`, `?markdown=`), applied to a fourth screen. `App.tsx` strips the query before it compares paths (D201), so a filter change does not remount the screen or reset its scroll.

`Pricing.tsx`'s two lenses write the hash directly, which pushes a history entry. That fits one discrete press. Revenue's search field fires on every keystroke. One history entry per letter would turn Back into an undo. So `writeUrlState` uses `history.replaceState` for every control on this screen, sort and month included. The trade: Back no longer steps through this screen's filter changes one at a time. Deep links and reloads still work, because both depend only on the URL's current string.

### Cross-filtering the month strip

The sparkline stays `aria-hidden`. A `<polyline>` is not an accessible control. Each row in the strip is now a `<button aria-pressed>`. The strip is the control itself, not a chip beside it. Selecting a bucket narrows the product table to that bucket's date range. The verdict and the chart stay scoped to the whole selected period. Only the product table narrows. The active filter appears as a dismissible `Pill` and `Button` pair above the table, reading `Aug 2026 only` and `Clear`. Pressing the same row again clears it, as the Clear button does.

A stale bucket cannot filter the wrong thing. Switching the period or the custom range clears the active bucket. The clearing effect skips its own first run. A deep link such as `?period=6m&month=2026-08` survives a reload.

### Drill-down

`Sale.order` carries the order's identity, `OrderRow.key`. A new field, `Sale.orderNumber`, carries its label, `OrderRow.number`. D56 and D145 already split an identity from what a person reads. A disclosure `<button>` in a new leading column expands a product row into a nested table: date, order number, copies, unit price. The order number draws in mono, as `Orders.tsx` does. The nested rows come from the same scoped sales the product totals use. Under an active month filter, an expanded row shows only that month's orders.

Expansion state is a `Set`, not one value. Opening a second row never closes the first. That is D118's argument, applied to a control whose result is new content. Nothing already on screen moves when another row opens.

### Custom range, and granularity from its width

Choosing Custom reveals two `<input type="date">` fields, `From` and `To`. The first time it is chosen, they default to the last 30 days. After that they read from the URL. Every window is anchored on the wall clock, `now`, not on the latest recorded sale. The three presets and the custom range share this anchor. "Ongoing" stays coherent: a store that sold nothing this week still has a "this month" that has not finished.

CLAUDE.md's citation names the research behind this choice. Stripe derives granularity from the range. Square offers a separate dropdown. This screen follows Stripe. The month strip becomes a week strip when the selected window's nominal span is 60 days or fewer. The threshold is chosen, not measured. It sits where a monthly bar would draw one or two bars, and a weekly one would draw eight or nine.

Only a bucket with a real sale draws. One exception: the bucket containing `now` always draws, even at $0.00, whenever the selection reaches today. A first draft zero-filled every gap in the span. It measured 75 words against the ratchet's old 56, mostly from empty historical months nobody asked to see.

### Partial-period honesty

The bucket containing `now`, when the selection reaches today, carries `inProgress: true`. It draws a small `Pill` reading "ongoing" beside its label. A half-finished month would otherwise read as a decline. The verdict does not assume that the prior window is complete. `elapsedMs` is how much of the current window has elapsed, clamped to `now`. The prior window is cut to that same length, from its own start, but never past the current window's start. On a few days a year it is up to about 3 days shorter. That reduces to the full-window comparison when the current window has fully elapsed, as in a closed custom range or all time. `compareLine` says so on screen: "So far, the period before this one made ...". The old comparison set 269 days of this year against 365 days of last year.

### Two defects fixed

- `compareLine` divided by the prior period's total with no zero guard. A recorded period can sum to exactly $0.00, and `salesOf` keeps a free line. The old code rendered `Infinity%` or `NaN%`. An explicit `previous === 0` branch now states the dollar difference in words.
- `name: line.name ?? line.sku` could put a raw SKU into the Name column with no mono treatment. `Sale.nameIsSku` is `true` only when the feed sent no name at all. The render site applies `bn-mono` to that one case. A real name is never wrapped in it.

### The copy-budget ratchet

`#/revenue`'s copy is measured with the `#/orders` fixture still live. `copy-budget.spec.ts` seeds real orders and never tears them down. The old ceiling, 56, already reflected that populated screen.

The new ceiling is 64, eight words higher. `Custom` on the period control costs one word. The comparison's "So far, " costs two, only when the current window has not fully elapsed. The `ongoing` bucket costs the other five: its month name, "ongoing," and "orders" against a zero count. It appears on the strip even at $0.00. Each of the eight was asked for in the brief this entry answers. `node scripts/copy-budget.mjs --pin` set the new number.

### Layout defects found in build

- A fifth `Segmented` option, "Custom", pushed `.bn-head-actions` 11px past a 390px width. It showed only once "Custom" was selected. The fix is narrow: `.revenue-period .bn-seg` wraps at 767px and below. It applies to this screen's instance of the shared `Segmented` control only.
- At 390px a numeric column's sort icon shrank under 1px. A bare SVG's flex `min-width` is 0, and the header's `nowrap` text left the icon nowhere to shrink. The fix protects the icon's width and gives the table's cells less padding at that width.

See also. D214 is the counting rules this entry does not touch. D103 and D277 are the `?…=` lens mechanism this entry reuses. D201 is the query-stripped `path` this URL mechanism depends on. D50 and D118 are the interaction floors. The sort buttons and the drill-down inherit them, as real `<button>` elements. D278 says a delta is a sign and a word. `compareLine` never colors "up" or "down". D193, D56 and D145 say an identity is not a label. This entry applies that to an order's key against its number.
