## D-revenue-slice — Sales becomes a tool: sort, filter, cross-filter, drill down and deep-link, over the same rows D214 already drew

**The problem this closes.** D214 built `#/revenue` as a retrospective. A verdict, a month
strip, a product table sorted by gross. The owner's own words: *"all we have right now is
just a notepad list of items sold and that is fucking it."* The table had one sort order.
The month strip drew a sparkline with `aria-hidden` and a row with no handler. Clicking a
month did nothing. Nothing on screen lived in the URL. A view could not be shared or
reloaded back into. A product's own orders were not reachable at all, though `Sale.order`
already carried them before being deduped away into `orderCount` and thrown out.

**Nothing about what counts as revenue changed.** D214's rulings stand untouched. Gross
only. Canceled dropped silently. Sealed and singles mixed on one list. No buyer detail. This
entry is about what a person can DO with the same rows, once they are on screen.

### Sortable columns

Name, Copies, Gross and Last sold each get a `<button>` inside their `<th>`. `aria-sort` is
set on the active column, `ascending` or `descending`, and left off the rest. That is the
ARIA APG shape, not a hand-rolled one. The first click on a column picks the direction a
reader wants first. Name goes ascending. Everything else goes descending: biggest gross,
most copies, most recent sale. A second click on the same column flips it. Gross-descending
stays the screen's own default, unchanged from D214.

### The URL is the one copy of the screen's own state, and it replaces rather than pushes

Period, search text, sort column and sort direction all live in `#/revenue`'s own query
string. So does the active month or week filter, and a custom range's two dates.
`readUrlState` reads it once at mount. `writeUrlState` writes it back on every change. This
is D103's own mechanism (`?band=`, `?markdown=`), applied to a fourth screen. `App.tsx`
strips the query before it compares paths. That is D201's own fact. It is what keeps a
filter change from remounting the screen or resetting its scroll.

**A deliberate departure from Pricing's own precedent, named rather than left to be found.**
`Pricing.tsx`'s two lenses write the hash directly. That pushes a browser-history
entry, correct for one discrete click. Revenue's own search field fires on every keystroke.
Pushing one history entry per letter would turn Back into an undo, one keystroke at a time.
`writeUrlState` uses `history.replaceState` instead, for every control on this screen, sort
and month included. That is one mechanism. It never behaves differently by which control
moved it. The trade, named plainly: Back no longer steps through this screen's own filter
changes one at a time. Deep-linking and reload-round-tripping both still work. Neither
depends on the history stack. Both depend only on the URL's current string.

### Cross-filtering the month strip

The sparkline stays `aria-hidden`. A `<polyline>` was never going to be the accessible
control. Each row in the strip is now a `<button aria-pressed>`. The strip itself is the
control the brief asked for, not a chip added beside it. Selecting a bucket narrows the
product table to that bucket's own date range. The verdict and the chart both stay scoped to
the whole selected period. Only the product table was asked to narrow. The active filter is
a dismissible `Pill` and `Button` pair above the table, reading `Aug 2026 only` and `Clear`.
Clicking the same row again clears it the same way the Clear button does.

A stale bucket cannot silently filter the wrong thing. Switching the period or the custom
range clears the active bucket. The clearing effect skips its own first run. A deep link
like `?period=6m&month=2026-08` survives a reload intact.

### Drill-down

`Sale.order` carries the order's identity, `OrderRow.key`. A new field, `Sale.orderNumber`,
carries its label, `OrderRow.number`. D56 and D145 already draw that same split, between an
identity and what a person reads. This applies it to one more record. A disclosure
`<button>` in a new leading column expands a product row into a nested table: date, order
number, copies, unit price. Those are the four fields the brief asked for. The order number
draws in mono, matching `Orders.tsx`'s own treatment. The nested rows come from the same
scoped sales the product row's own totals are built from. An expanded row under an active
month filter shows only that month's orders, never the whole period's.

Expansion state is a `Set`, not one value. Opening a second row never closes the first. That
is D118's own argument. It is applied here to a control whose result is new content, not a
size change to itself. Nothing already on screen moves when another row opens.

### A custom date range, and a granularity chosen from its width

Selecting Custom reveals two `<input type="date">` fields, `From` and `To`. The first time it
is chosen, they default to the last 30 days. After that they read straight from the URL.
Every window is now anchored on the real wall clock, `now`, not on the latest recorded sale.
The three presets and the custom range all share this anchor. It is what makes "ongoing"
below a coherent idea. A store that sold nothing this week still has a "this month" that has
not finished yet.

CLAUDE.md's own citation names the research behind this choice. Stripe derives its
granularity from the range. Square offers a separate dropdown for it instead. This screen
follows Stripe's shape. The month strip becomes a week strip when the selected window's
nominal span is 60 days or fewer. That threshold is chosen, not measured. It sits at the
point a monthly bar would draw one or two bars, and a weekly one would draw eight or nine.

Only a bucket with a real sale draws, the same rule the screen always followed. One
exception: the bucket containing `now` always draws, even at $0.00, whenever the selection
reaches today. A first draft zero-filled every gap in the whole span instead. That draft
measured 75 words against the ratchet's old 56, mostly from empty historical months nobody
asked to see. This entry's own copy-budget section states the final, smaller cost.

### Partial-period honesty

The bucket that contains `now`, when the selection reaches today, carries `inProgress:
true`. It draws a small `Pill` reading "ongoing" beside its label. A half-finished month
would otherwise read as a decline on the chart. This names that fact instead of leaving it
to be misread. The verdict's own comparison no longer assumes the prior window is complete.
`elapsedMs` is how much of the current window has actually elapsed, clamped to `now`. The
prior window is cut to that same length, starting from its own beginning. This reduces to
the old, full-prior-window comparison in one case. The current window has already fully
elapsed: a closed custom range, or all time, which has no prior window at all. It truncates
the comparison in every other case. `compareLine`'s own wording says so on screen: "So far,
the period before this one made ..." That sentence replaces a silent comparison. The old one
compared 269 days of this year against 365 days of last year.

### Two defects fixed

- `compareLine` divided by the prior period's total with no zero guard. A real, recorded
  period can sum to exactly $0.00. `salesOf` only drops a non-finite price, so a free line
  stays in. The old code rendered `Infinity%` or `NaN%` for that case. The fix adds an
  explicit `previous === 0` branch. It states the dollar difference in words, rather than
  dividing by zero to get one.
- `name: line.name ?? line.sku` could put a raw SKU into the Name column with no mono
  treatment. CLAUDE.md already states this rule. `Pricing.tsx` already follows it for the
  same fact (`bn-mono`). `Sale.nameIsSku` is `true` only when the feed sent no name at all.
  The render site applies `bn-mono` to that one case. A real name is never wrapped in it.

### The copy-budget ratchet moved, on purpose, and by the least this could cost

`#/revenue`'s own words are measured under a leaked fixture, not the empty state this file
first assumed. `#/orders` comes before Sales in the nav. `copy-budget.spec.ts` seeds it with
several real orders and never tears that stub down. So `#/revenue` is measured with that
same data still live, not with zero orders. The old ceiling, 56, already reflected that
populated screen.

The new ceiling is 64, eight words higher. `Custom` on the period control costs one. The
comparison's own "So far, " costs two, only when the current window has not fully elapsed.
The `ongoing` bucket costs the other five. It is forced onto the strip even at $0.00. Its
own words are a month name, "ongoing," and "orders" against a zero count. Every one of the
eight was asked for by name, in the brief this entry answers. `node scripts/copy-budget.mjs
--pin` set the new number, and this session did not pin quietly.

### A layout defect this build found in itself

A fifth `Segmented` option, "Custom", pushed `.bn-head-actions` 11px past 390px width. The
overflow was invisible from the screen's own resting state. It showed only once "Custom" was
selected. It was measured with a script, not assumed from a screenshot. The fix is narrow.
`.revenue-period .bn-seg` wraps at 767px and below. That is scoped to this screen's own
instance of the shared `Segmented` control. No other screen that uses it is touched.

The same pass found a second defect. A numeric column's own sort icon shrank to under 1px
wide at 390px. A bare SVG's flex `min-width` is 0. The header's `nowrap` text gave it nowhere
else to shrink to. The fix protects the icon's width. It also gives the table's own cells
less padding at that width.

See also. D214 is the counting rules this entry does not touch. D103 and D159 are the `?…=`
lens mechanism this entry reuses, a third and fourth time. D201 is the query-stripped `path`
this whole URL mechanism depends on. D50 and D118 are the interaction floors. The sort
buttons and the drill-down inherit them free, as real `<button>` elements. D62 says a delta
is a sign and a word. `compareLine` never colours "up" or "down". D193, D56 and D145 say an
identity is not a label. This entry applies that to an order's key against its number.
