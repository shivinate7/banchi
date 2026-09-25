# Pricing deliberation: what the owner decides, and a screen built around it

**Status: reasoning, not a spec.** The final answers live in `RULINGS.md`'s "Pricing
re-interview" section. This file holds the measured evidence, the proposal's own shape, the
alternatives the owner did not pick, and the decisions the change touches. The b-pricing lane
reads both.

## The verdict

Pricing is built as a form the owner fills in, row by row. The product's own mission is the
opposite: zero attention per card. The rule already fills in every run row, so most rows need
no press. The screen draws every row the same, at full weight, below 600px of chrome, so the
owner cannot see which rows need attention.

The recommendation: show the rows that need the owner, and fold the rest into counts. One slim
bar says how many copies are ready, and holds the one Send press. The store rule and the
cut-off become one line. Every product name opens the one product sheet. Mark-down becomes a
"Live" tab.

Measured on the demo store, 30 SKUs, against the built screen:

| | As built | Proposed |
|---|---|---|
| First row, 1440 | 680px down, 2 rows above the sticky bar | 266px down, 8 rows in view |
| First row, 390 | 1,174px down (1.4 screens) | 329px down |
| Row height, 390 | 260px (1.5 rows a screen) | 77px (about 8 rows a screen once scrolled) |
| Sticky bar, 390 | 174px | 52px, one line |
| Chrome words above the first row, 1440 | 189 | 45 |
| Price field, 1440 | 9px wide, cutting off a typed price | 116px, sized for "$999.99" |
| Page height, 390 | 9,676px | about 2,200px |

## Pricing as built

`Pricing.tsx` runs 5,065 lines over 12 components, with `Pricing` itself over 3,300 of them.
Three modes share one route: the worklist (unsent copies from joined runs), the mark-down lens
(`?markdown=<stamp>`, the live export), and the value lens (`?band=top|bottom`, read-only,
linking out to Inventory). Only two places in the code ask which mode is live.

Two defects the walk found beyond what `CONSOLIDATED.md` already lists. First, the demo opens
on one run on purpose, because history and trend routes are per-run. On the owner's real
landing, where every run loads at once, the history press and trend loading are dead. A product
sheet that reads by SKU rather than by run avoids this. Second, the price field is 9px wide at
1440 only while the Compare toggle sits off. Compare on gives it 116px, so the narrow-field
defect (UX-002) is a default-state bug, not a universal one.

Every typed price on the demo already equals a rule's price to the cent. 11 rows sit at market
plus 8 percent, and 10 rows sit at the $0.49 cut-off exactly. On the demo, typing bought
nothing over letting the rule run. Whether the owner's own store shows the same pattern is unmeasured (see
"Measure before building").

This proposal closes UX-007, 035, 066, 068, 070, 083, 085, 115, 135, 144 and 146 on layout and
density. It closes UX-002, 043, 054, 058, 059, 071, 073, 075, 107 and 108 on fields and
controls. It closes UX-045, 053, 084, 103, 105, 106, 120, 131 and 160 on words (Near Mint
stays, by the owner's own exception ruling). It closes UX-003, 017, 026, 027, 031, 042, 078 and
097 on flow and links, and every TXT-06 through TXT-15 density cut except TXT-07 (also kept by
ruling).

## What the owner decides on Pricing

| Decision | How often | Today | What the screen can do |
|---|---|---|---|
| The store rule (match, under, over market, or lowest) | rarely | a four-way strip on every visit | one line, changed in a sheet |
| The cut-off | rarely | its own card on every visit | the same line |
| A price for a row with no market price | per row, blocking | a trailing section blocks the whole write | put it first, and never block the rest |
| A price for a row worth a look (high value, drifted, an odd market) | per row, some | nothing marks these rows | flag them, and put them first |
| Hold a card back | per row, rare | an icon and a popover | the same, from the row and the product sheet |
| How many copies go | per row, rare | a field on every row | shown only when it matters |
| When to send | per sitting | write, download, then upload in the portal | one press |
| Which listings to mark down | per sitting, a separate job | a long sheet, then a lens | a Live tab |

Everything else on the screen shows the machine's own work. It can pre-fill from the market
already, so the owner never confirms a row that needs no confirming. It can batch-accept by
default, so an untouched row still goes out at the rule's price. It can offer the rule back,
when typed prices already follow one pattern. It can load trends only for the rows that need a
human, and only after that cost is measured.

## The proposal's shape

**The header** reads "Pricing", with tabs for "To send" and "Live", a shared search field, the
shared filter, a More menu, and reload. The filter replaces the old Runs picker. More holds
"Clear my prices", "Download the file instead" and "Check what is live".

**The slim bar** states four counts: ready, needs a price, held, and already live, beside the
split Send button. It carries no legend of its own, because the words already say what they
mean. It stays sticky at the top on desktop and at 720. On a phone it pins one line above the
tab bar.

**The rule line** reads the rule and the cut-off in one sentence. "Change" opens one sheet
that holds the rule presets, a custom rule, the cut-off, and a box's own cut-off. The old deck
card goes.

**Needs you** lists the rows a human must answer, each with one flag chip. "No market price" is
red and blocks only that row. "Worth over $5", "Your price is far under market" and "Lowest is
far under market" are amber flags.

**Ready** lists every other row that will go out, highest market value first. The rule's
price already sits in the field, and a check mark marks any row the owner typed over.

**Fold lines** collapse the routine cases into one line each: the copies at the cut-off, the
held cards, and the cards already live. Each opens on "Show".

**After Send**, the bar's state changes in place and keeps its own height, so nothing else on
the screen moves. It steps through sending, live and waiting on the check, some copies not
landed, checked, and downloaded but not yet confirmed (with "Take them back" once its own wait
has passed).

**The row itself** carries the photo, the name (which opens the product sheet), and the meta
line, with Near Mint kept. It also carries the market price, the lowest price, a spark line,
the price field in mono, and Hold. On a phone it drops to two lines. Rarity leaves the meta
line, and Lowest moves into the sheet.

**The product sheet** is a right-side sheet on desktop and a bottom sheet on a phone. Its head
holds the name, the meta line, the price field, Hold, and "Open as page". Its History tab draws
market, lowest, and lowest with shipping, plus a chart and a list of the owner's own sales. Its
Photo tab shows this copy. It reads by SKU, so it still works on the all-runs landing where
today's drawer goes dead.

**The Live tab** draws the same rows for mark-down. The field opens empty with the asking price
as a ghost. The settings collapse into one line with "Change".

**What leaves the screen entirely**: the legend, the run id in the scope line, and the
progress bar. Also the Saved pill, the deck, the rule strip, and the Compare toggle. Also the
keyboard hint row, which moves into the `?` sheet, and every decision argument printed as
screen copy.

## The alternative the owner did not pick

**A review-style pass, one card at a time.** The bar and the rule line stay. The "Needs you"
rows open as a queue, like `#/review`: one large photo, the history chart, market and lowest,
the price field, and Hold. Enter takes the price and moves on. The ready rows stay counts only.

This wins on keeping the photo and history always in view, with no sheet to open. It is fast
by keyboard, and good on a phone. It loses on comparing rows side by side, and it adds a second
interaction pattern beside Review itself. It is slow once "Needs you" runs to forty rows.
It was not preferred, though it may fit a short "Needs you" list. It is worth a second look if
the owner's own store measures fewer than about ten rows a sitting.

A second alternative kept today's sections, and applied only the slim bar, the fixed field, the
density cuts and the product sheet on top. It is the smallest possible build, and the fallback
if the owner had picked "every row split at the cut-off, as today" over the show-only-what-
needs-you shape. The owner picked the fuller reshape instead.

## Decisions this touches

| Decision | Outcome it protects | What changes |
|---|---|---|
| D208, one verdict on Pricing | one statement of where things stand | The deck goes. The bar is the verdict. |
| D156, one worklist, everything unsent | no copy forgotten | Kept. The Runs picker becomes a Box filter. |
| D49, D86, the blocking rule for a missing price | a missing price reads as unknown, never low | The row with no price still cannot go. The rest can. |
| D99, the cut-off is one variable | one figure, one line | Kept, on the rule line. |
| D7, quantity and a cap per send | a copy is never sent twice | Kept. The quantity shows only when it matters. |
| D62, D227, history beside the hold, and a route | history stays in reach from the row | The product sheet reads by SKU. The route stays. |
| D103, D105, the mark-down lens and sheet | mark-down lives where prices are decided | The lens becomes the Live tab. |
| D106, push and publish are two presses | a buyer sees nothing without a press | Listings now send in one press. Mark-downs follow the same ruling. |
| D159, the value lens on Pricing | a pull list by value | It moves to Inventory. |
| D168, a typed price clears by a press | nothing expires on its own | Kept, moved into More. |
| D137, Near Mint by rule | the label stays uniform | Shown on every row, by the owner's own exception. |
| D221, money stays mono | one face for money | Applied to fields and chips too. |
| D118, a press never moves the rest | stability | Release keeps the row. The bar keeps its height. |

A "needs you" flag set, and a send that skips only the blocked rows, are new behaviour. Each
needs its own decision entry once the b-pricing lane builds it.

## Measure before building

None of these ran here. Each is a read against the owner's own store.
1. Count the unsent rows each "needs you" flag level would catch, to size the list and to
   choose between the proposal and the one-card-at-a-time alternative.
2. The share of typed prices in `prices.json` that already equal a rule's figure to the cent.
3. How many unsent rows carry no market price at all.
4. The time to load a seven-day trend by SKU for only the flagged rows.
5. Whether the by-SKU history answers correctly on the all-runs landing, as the product
   deliberation expects.

## Options each ruling weighed

Every answer below is now recorded in `RULINGS.md`'s "Pricing re-interview" section. This keeps
only the alternatives the owner did not pick.

- **What shows first?** Only the rows that need you, with the rest as a count (chosen). Or
  every row, needs-you on top, the rest by value. Or today's cut-off split.
- **Which rows need you?** No market price alone. Or that, plus $5-or-more value. Or that,
  plus a typed price far from market (chosen, pending the store measurement). Or that, plus a
  lowest listing far under market.
- **What does Send do with an unpriced row?** Send every ready copy and leave the rest on the
  list (chosen), or block every send until every row has a price, as today.
- **Where does the bar sit?** Sticky at the top on desktop and 720, one line above the tab bar
  on a phone (chosen). Or fixed to the bottom on every width. Or fixed to the top on every
  width.
- **Where do the rule and cut-off live?** One line with a Change sheet (chosen), a smaller
  version of today's card, or a settings screen.
- **How does mark-down work?** A Live tab with the same rows (chosen), or today's sheet kept,
  then the lens.
- **Does one press cover mark-downs too?** Yes, with a way back (chosen, though a true rollback
  in one press stayed unmeasured at the time of the ruling), or mark-downs keep two presses.
- **Where does the value list go?** To Inventory, as a sort (chosen, since it prices nothing and
  every row already links there), a third Pricing tab, or a header button as today.
- **Does Pricing ever offer to adopt a pattern as the rule?** Yes, once, when most typed prices
  already match one pattern (chosen, pending the store measurement), or never, so the owner
  changes the rule by hand.
- **What goes under the Send arrow?** A per-card cap and an above-cut-off filter, with the
  file split moved under "Download the file instead" (chosen). Or all three controls kept
  beside Send, as today. Or none of them.
