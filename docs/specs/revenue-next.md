# Sales: what is wrong with it, and what comes next

**Recorded 2026-09-19. Not built.** D217 shipped the interactive Sales screen. D216 repaired the
price history reader the same day. This file records what five independent reviews found
afterwards. It also records the work the owner deferred. Nothing here is built. Nothing here is
approved, except where it says so.

Read D214 for why the screen exists. Read D217 for what made it interactive. Read D62 for the
price history rules that every future chart inherits. Read D216 for why that reader needed a
repair.

## 1. Confirmed defects

Ranked by how wrong a decision each one could cause. None is a data error. All are real.

### The comparison sentence marks the wrong period

`compareLine` builds one `lead` string. It shares that string across every branch. When the
current window is unfinished, `lead` becomes `So far, the period before this one made`. The words
`So far` then modify a closed window's total. That is false. The closed window is over. The
qualifier belongs on the current total instead.

The owner found this first in the empty branch. There it reads
`So far, nothing is recorded for the period before this one`. The defect is not confined to that
branch. The same string fires on the ordinary comparison. That is the default six month view. It
fires every day of every unfinished month.

No test opens the screen at its own default period against a populated prior window. The most
common sentence on the most common view has no coverage.

### The month chart hides a gap month

A bucket is created only for a month that carries a sale. The month containing now is the one
exception. A month with zero sales is never added at all. It is not added as a gap. It is not
added as anything.

The geometry function spaces points by array index. Two months on either side of an empty one are
therefore drawn as neighbors. The break logic in that function cannot fire here. A bucket's gross
is always a real number and never absent. That logic was written for a price series on a fixed
calendar grid. This is a variable length list of populated months. The two shapes differ.

The current data has no gap month. The chart is correct today. It will mislead on the first month
that sells nothing.

### The chart rescales itself and can invent a crash

The geometry function normalises to the lowest and highest value in view. Slope therefore carries
no absolute meaning. The same dollar gap draws steeper or flatter, depending on what else sits in
the window.

A reviewer reproduced this on a seeded store. At two buckets the line drew a full height plunge.
At three buckets it drew a spike and then a cliff. Neither was a crash. The low bucket in both
cases was the unfinished current period.

### The unfinished period is not marked on the chart

The month list marks it with a pill. The chart does not. There is no dashed segment and no marker.
Nothing in the chart reads the in-progress flag.

The real data holds a five fold swing. A reader takes the final slope as a signal. August closed
at $14,071.40. September stands at $11,814.18 across 19 days of 30. That draws as a decline.
September's daily rate is in fact the higher of the two.

### Percent change has a zero guard but no floor

The guard fires only at exactly zero. A prior period of five cents against a current fifty dollars
renders as a five figure percentage. It is drawn at the same weight as any other figure. D62 set
the house convention for this. An anchor carries one weight and a bound carries another. This
screen does not carry that convention over.

### Drilling into the unfinished period loses that fact

Selecting the current month narrows the product table. Nothing in that table repeats that the
month is still running. The filter chip does not say so either. Copies, gross and last sold are
drawn at the confidence of a closed month.

### Three house rules are not followed

**Numbers in a table are set in mono.** `CLAUDE.md:321` states that numbers in tables are the user
face with tabular figures, and not mono. The `bn-money` class is mono. `Revenue.tsx:811` and
`Revenue.tsx:832` apply it inside a table cell. The order number beside it is correctly mono,
because an order number is a machine string. Two different kinds of information now share one
register.

**The rule and the primitive disagree, which is the deeper finding.** A comment at
`RunPanel.tsx:226` argues that `bn-money` is the treatment a column of dollar amounts needs. One
of those two statements has to give way. That is a repository level question and not a screen
level one.

**List rows do not stagger.** The house rule is written in `CLAUDE.md`. The mechanism is
`bn-stagger` in the kit. Home and Orders both use it. The word `stagger` does not appear in
`Revenue.tsx` or in `Revenue.css` at all. Every month row and every product row appears at once.

**The verdict figure carries no weight of its own.** The whole sentence is one flat string at one
size and one weight. The dollar figure reads at the same weight as the word `over`. Pricing wraps
the key figure of every verdict in a strong tag. That pattern was not carried across. The fix adds
one tag and no words.

### Two layout defects at 390 pixels

Order numbers clip in the middle of the string, inside the per order drill down. An order number
that cannot be read cannot be looked up.

The product name column has no height cap. Real names wrap to two lines. The numeric columns stay
on one line beside them. Row height is therefore decided by the longest name in that row. Numeric
baselines drift down the table. A real data table holds one row height and truncates the identity
column instead.

The fifth period option wraps onto its own row and sits alone. It reads as a stray control rather
than one choice of five.

### What the tests do not constrain

Seventeen cases cover sorting, filtering, URL round trips and the drill down. The arithmetic is
almost entirely unguarded.

There is no test of the default period's ordinary comparison sentence. There is no assertion of
any kind against the chart's rendered geometry. No fixture carries a gap month. No fixture carries
an order of more than one line. The de-duplication that produces the order count is therefore
exercised only by data that could not expose a fault in it.

## 2. The refund hole

This is a correctness problem and not a disclosure problem. It is the most consequential finding
in this file.

The screen excludes exactly one status word. A refund does not reliably produce that word. Neither
does a return or a partial cancellation. Refund data is dropped at the transport boundary and
never stored. Nothing downstream can see one.

A sale that is later returned stays counted as revenue for good. There is no decrement and no
flag. There is no mechanism by which the figure could ever notice.

D214 reasoned carefully about an order that was never a sale. Nobody asked the inverse question. A
sale already counted can stop being one. The number drifts high over time and says nothing.

No refund data exists to collect today. The minimum honest response is to say so on the screen.
Not holding the data is a constraint. Not disclosing it is a choice.

## 3. What the five reviews said

Five reviews ran on 2026-09-19 against the merged screen. Each was briefed to hold one point of
view rather than to be balanced.

### Dense operator tooling

The screen binds no keys of its own. The search key it appears to own belongs to a shared
component. Every screen using that component inherits it. Pricing binds nine single key actions
for its repetitive work.

Sales has no repetitive per row action yet. A full set of keys is therefore not obviously
warranted. Two gaps are still real. The five period presets are reachable only by pointer. The
month filter can be cleared only by pointer, although Escape already means dismiss everywhere else
in this shell.

The highest value change identified was a share of total column on the product table. The
denominator is already in scope. The cost is one cell per row. Revenue is concentrated in sealed
product across 539 names. This converts a flat list into the ranking the screen exists to answer.
It does so without faking the split that the wire cannot support.

An average unit price column was named second. A high unit price against a low copy count is the
honest signal for sealed product. It is computed rather than guessed.

The unpaginated table was judged correct and not a defect.

### Small business accounting

The headline word is correct accounting English. A reader who is not an accountant will still read
it as what they made. The caveat appears once, above the figure, in the quietest available weight.
Later currency figures on the screen carry no reinforcement at all. The recommendation was
repetition at the point of reading.

There is no export of any kind. Every other money surface in this repository produces a file. This
is the one screen whose figure a tax preparer would want. It exists only as a rendered page in one
browser session.

The screen groups by when an order was placed. It does not group by when money arrived. Compared
against a marketplace's own annual statement, that difference reads as a software fault. It is a
timing convention that nobody stated.

### Brokerage conventions

This is a trade blotter and not a portfolio view. It shows no position, no quantity held and no
basis. Calling it Sales is honest. Language elsewhere edges toward a register it has not earned.

A rule to write down before anyone builds a cost basis field. A lot with unknown basis is labelled
unknown. It is never assumed to be zero. It is never blended into one aggregate gain figure beside
lots whose basis is known. Every historical lot in this store would be unknown. Blending is the
most likely way this product eventually lies to its owner.

A comparison against the market at the time of sale is a measure of pricing quality. It is never a
measure of performance. The two are easy to blur. It is blind to acquisition cost. A card bought
at two dollars and sold at eighteen against a twenty dollar market reads as money left on the
table. It is in fact a large gain. The figure must never be labelled performance or gain. It must
never sit near the word revenue.

One recommendation was to refuse a feature the owner asked for. Comparing a completed sale against
today's price inverts what a realized gain means. The money was taken. No risk was carried
afterwards. The figure still renders as a loss. Unrealized gain belongs only on a position still
held. **This is the owner's call and is not settled.** Two narrower forms preserve most of the
value. Scope the comparison to unsold stock, which is the legitimate marking to market question.
Frame the sold side as pricing quality, with no currency sign implying money lost.

Marking unsold stock to market must carry the age of each mark. It must also carry a count of
names excluded for having no mark at all. Both belong on the same screen as any total. The screen
already does exactly this for lines it drops. That is the pattern to inherit.

### Inferential rigour

Section 1 is drawn from this review. Two further findings are plausible rather than confirmed.

Preset comparison windows may overlap the current window by one to three days. This would happen
at the instant a period closes. The previous window's end is derived from elapsed milliseconds
against a calendar anchored start. Month lengths differ between blocks.

Gross is accumulated in floating point across 1,268 currency additions. There is no integer cent
accumulation. Drift is possible in kind. No discrepancy has been measured.

### Modern product design

Findings are folded into section 1. One recommendation stands apart and is a subtraction.

**Delete the chart.** It duplicates the list beneath it. It is less honest than that list, for the
three reasons recorded above. It carries no axis, no points and no recoverable value. A reader
cannot take a dollar amount from it. Every real number is already in the list below.

If a shape is still wanted, put a proportional fill behind each row's own value. That inherits the
row's real scale rather than inventing its own. It is one widget rather than two. It adds no
visible words.

## 4. Deferred work

Both items are the owner's. Both were deferred on 2026-09-19. The scheduler is explicitly out of
scope.

### The archive comes first

The price history source has a hard ceiling of 357 days. No deeper window exists. Everything older
is already unrecoverable. Everything not captured from now on ages out on the same schedule.

**This is the only time sensitive item in this file.** A screen can be improved next month. A
bucket that ages out cannot be recovered at any later date.

The house pattern to follow is the existing readings table and its adopt command. That is a table,
a deliberate press that fills it, and an accounting of what each pass read.

Buckets must be keyed by bucket width, as well as by product and start date. The ranges overlap.
One day appears as a one day bucket in one range. The same day sits inside a seven day bucket in
another. Those are two different facts. They must never be merged. D62 forbids joining ranges and
that rule survives into storage.

A sweep across the names the owner has sold or holds was measured at about one second per cold
name. The owner chose a scheduled sweep. The schedule is deferred and the sweep comes first. The
timer reverses D62's statement that this reader cannot fire on its own. That reversal needs its
own argument.

### The per product view comes second

One page per product, deep linkable. It shows what a product has been selling for. It marks the
owner's own sales on that line.

The owner's own sales are exact fills. Each one carries a price, a quantity and a date. There are
1,268 of them. The market series is an aggregate. Each bucket describes many transactions. It
carries a market figure, a low, a high and a quantity.

These are two different kinds of observation. Every rule below descends from that.

- The market series and the owner's fills may never be drawn as one continuous series. Use
  different marks and a legend. Never use the same line.
- The aggregate's own spread must be carried and not discarded. D62 measured a band 48 percent of
  the estimate wide on a real card. A single number comparing a fill to a bucket states a
  precision that the source refuses to claim.
- Direction is a sign and a word, and never a color. This is D62's rule. The palette holds no red
  and no green, deliberately. Coloring a fill as beating or missing the market is exactly where
  this would break.
- A bucket with no price breaks the line. It is never interpolated across. That rule already
  exists for the price panel. It must be inherited rather than rebuilt.
- The chart must state the date its own history begins. A year of local archive is not a year of
  market history. Nothing may backfill the difference with an assumption.
- A sale older than 357 days has no market data at all. What draws for those rows must be visible
  and must say so.
- Bucket width depends on when the report is read. It does not depend on when the sale happened.
  One sale sits in a one day bucket today. The same sale sits in a seven day bucket months later.
  Nothing about the sale has changed. Reported precision therefore decays over time for a fixed
  fact. The width must be stated.
- Weekly buckets are stamped at the start of their week. Matching a sale to a bucket therefore
  carries a boundary ambiguity of several days beyond the 87 day mark.
- A counterfactual priced at one figure assumes the market absorbs the whole quantity at it. The
  same source proves otherwise, bucket by bucket, through its own quantity field.
- The current price feed is at product and printing level. It is not at condition level. Comparing
  a condition specific historical sale against a blended current figure is not the same card.

## 5. Open for the owner

1. The comparison against today's prices, against the argument recorded above. Refuse it, scope it
   to unsold stock, or frame the sold side instead as pricing quality.
2. Whether a refund disclosure goes on the screen now, given that no refund data exists.
3. Whether an export is built, and of what.
4. Whether the chart is deleted, repaired or left alone.
5. Whether the mono treatment for money in a table follows `CLAUDE.md:321` or follows the kit's
   own comment. One of the two has to give way.
6. Whether cost basis is ever captured, and at what grain. The reviews agree that unknown basis
   must be labelled and never blended, whatever grain is chosen.
