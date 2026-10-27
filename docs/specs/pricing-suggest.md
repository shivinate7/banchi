# Pricing by suggestion: one list, one rule, you confirm

**STATUS: MOCKUPS SIGNED OFF. BUILD MAY START.** The owner signed off the one-list mockup,
`docs/design/pricing-suggest/list.html`, and picked the floating history card,
`docs/design/pricing-suggest/history-float.html` (section 9c). Section 4b judges each trigger.
The suggestion limit and the value line are owner settings that start at 25% and $25
(section 5, step 3).

The problem: `#/pricing` has two tabs with two rule systems. Unsent cards use a rule and a
cut-off. Live listings use days unsold, a percent under the asking price and a dollar cap. One
price line has many names. The price field does not say whether a price came from the rule or
was typed. Old live listings drift from market and nothing says so. The owner called the tools
"bad and unintuitive".

---

## 1. The owner's rulings

| Question | Ruling |
|---|---|
| Rows shown before a send | **Every row, made clearer.** Not an exceptions-only list. |
| Live listings follow the market | **Suggest, the owner confirms.** No live price moves without a press. |
| Triggers for a suggestion | **All four are candidates**: market moved, unsold for N days, undercut by others, card selling fast. Each is judged with mockups before the build. |
| How far one suggestion may move | **A cap both ways.** Moves inside the cap go in the one-press batch. Bigger moves show apart and need a tick. |
| List layout | **One list, groups on top**: Needs you, Suggested changes, Going at the rule. |
| The rule's anchor price | **Measure first.** Count which anchor, per value band, best matches the owner's typed prices. Then pick. |
| Value bands | One of several aids. Not the whole answer. |
| The floor | **The owner sets it.** The repo holds no derived floor figure. |

## 2. The model

- **One list** holds new copies and live listings. The Unsent and Live tabs merge.
- **One rule** prices both. It starts from an anchor price (section 1, measure first) and
  clamps to the owner's floor.
- **A suggestion** is a proposed price for a live listing. A trigger raises it. It carries a
  reason in words, such as "market up 18% since listed" or "unsold 30 days".
- **Every row says where its price came from**: Rule, You (typed), Floor or Suggested.
- **Send** is one press. It sends new copies, kept suggestions and typed prices together.
  D273 (one press sends listings live) still holds.
- A suggestion may raise a price, up to the cap. The owner reopened D107 (a typed price goes
  either direction, and only the rule never proposes a raise) for it: section 5, step 4.
  D100 (never delete to lower a price) stands.

## 3. Groups, top to bottom

1. **Needs you.** No market price, a move past the cap, or a card at or above the value line.
2. **Suggested changes.** Live listings with a suggestion inside the cap, ticked by default.
3. **Going at the rule.** Everything else. It is still on screen, and each row shows its source.

## 4. Data each trigger reads

| Trigger | Data | Exists today |
|---|---|---|
| Market moved | Market at listing day against market now | Yes. The daily catalog read and the price archive (D219, the archive never deletes). The archive sweep runs only on a press (DEBT32, the archive sweep stays a press). |
| Unsold for N days | Listing age and the last sale here | Yes. `first_seen_live` and the order ledger (D109, listing age). |
| Undercut by others | Low With Shipping | Yes. Stored, and read by no rule. |
| Selling fast | 30-day market-wide units sold | Yes, for listed cards. It is market demand, not this listing's sales. A held card that is not listed gets no daily read (DEBT69, the price refresh schedule). |

## 4a. How often each trigger fires

A read-only count over the owner's store and the newest live export, from the main checkout. No
network, no spend. The store held 914 live listings. The export gives our asking price for 901
of them. A live market reading exists for 498. Thresholds here are samples for the count, not
proposals.

| Trigger | Sample threshold | Fires on | Out of |
|---|---|---|---|
| Market moved | 10% / 15% / 25% from listing day | 316 / 244 / 149 | 480 with a reading and a history |
| Unsold for N days | 14 / 30 / 45 / 60 days | 901 / 745 / 383 / 0 | 914 |
| Undercut by others | Low With Shipping 5% / 10% / 20% under ours | 24 / 20 / 15 | 498 with both prices |
| Selling fast | 5 / 10 / 30 units sold market-wide in 30 days, ours under market | 12 / 12 / 10 | 498 |
| Past a 25% cap | market more than 25% from our asking price | 347 | 498 |

Two facts shape these numbers. The listings arrived in waves: 383 first went live on one day
and 370 on another, and no listing is older than 45 days. So none fires at 60 days today, and
the whole first wave crosses 60 days on one day. And `sold_here` reads 0 on every live
listing, so "unsold" here is an upper bound: a build must read the order ledger instead.

## 4b. Judgment of each trigger

The owner rules on each from the mockups (`docs/design/pricing-suggest/list.html`). These are the
recommendations.

- **Market moved: keep, as the main trigger.** It is the one signal with volume and meaning.
  At 15% it fires on about half the listings with data, so the cap matters: 149 move more than
  25% from listing day, and 347 sit more than 25% from market now. Those land in Needs you. Each row says the direction and the sold range behind it.
- **Unsold for N days: do not keep alone.** By age alone it fires on 745 of 914 at 30 days, and
  a whole wave crosses any threshold on the same day. It says "time passed", not "price is wrong". Keep
  it as a qualifier: unsold N days AND our price above market. Then it names a real lowering.
- **Undercut by others: keep, quiet.** It fires on 20 of 498 at 10%. Low With Shipping is already
  stored. It is cheap and rare, so it adds little noise. The row must say the price includes
  shipping.
- **Selling fast: fold into market moved.** It fires on 12 of 498. Its data is market-wide demand, not
  our listing's sales, and an unlisted card gets no daily read (DEBT69, the price refresh
  schedule). Show units sold as evidence on a market-moved raise, not as its own trigger.
- **Outside signal: a slot, not a trigger.** A reason line such as "meta: played in a winning
  deck" can carry a signal from outside, like the Riftbound meta research. Nothing builds it now.

## 5. Before the build

1. **Measure the anchor.** A read-only count over the owner's store, from the owner's main
   checkout: per value band, the share of typed prices that each anchor (Market, Low, Low With
   Shipping) matches within a few cents. It extends the measurement in DEBT41 (pricing never offers "make this the rule"). No network, no spend.
2. **Mockups.** The one list at 1440 and 820, both themes. Show each trigger's suggestion row
   and the cap's flagged row. The owner judges each trigger from the mockups.
3. **The cap and the value line are owner settings.** They start at 25% and $25, and the owner
   changes either in one press, as with the floor. These starting values are the orchestrator's
   pick, not an owner ruling. At 25%, about 347 of 498 priced live listings land in Needs you on
   day one.
4. **Reopened, on the owner's word.** A suggestion may raise a price, up to the cap. New
   copies and live listings share one list. This reopens D107 (only the rule never raises: the
   cap is its raise ceiling), D105 (mark-downs live where prices are decided: they become rows
   of the one list) and D277 (pricing lists all rows: its Q6, the Live tab, goes). D103
   (staleness filters, never gates) stands.

## 6. Clarity fixes that stand alone

These do not wait for the model. Each can land first.

- One name for the price line on screen. "Cut-off" says nothing is cut off. A $0.05 card lists
  at the floor.
- Each row shows its price source.
- A preset shows how many rows change and the dollar difference before the press.
- A crossed hold watch ("alert when market is above") shows on its row. Today only the join
  report prints it.
- One word for the owner's choice to keep a card back. It must differ from the send guard's
  trim, which also says "held back".

## 7. Stale text to rewrite

The owner sets the floor, and it has not been the code default for months. These texts still
present a fixed or derived figure:

- `pipeline/pricing.py`'s module header derives the floor from a $60/hr labor bar at $0.40. It
  also says cheap cards leave through Bulk Lots. `pricing.THRESHOLD` and `pricing.FLOOR` are
  module defaults, and the header must say so.
- D9 (threshold and floor) must say the owner sets the floor, and name the default as a default.
- CLAUDE.md's line "`sub_threshold` defaults to $0.49" is a default, not the floor.

## 8. What this does not do

- No automatic live price change. A bounded automatic mode needs its own decision.
- No fee model. A floor computed from TCGplayer's fees needs the owner's real fee rate.
- No bulk-lot path.

## 9. More tools

The owner asked for "more tools at hand". Several exist already. The owner's rulings and the
open questions:

| Tool | What exists | Status |
|---|---|---|
| Price history | A trend line on each row (`PriceTrend`). The full chart on the product sheet, one press away (D278, one product view, two frames). | **Ruled: the floating card.** It opens by itself when a price field takes focus. Section 9c. |
| Comparable sales | Per period: copies sold, sale count, lowest and highest sale price (`pipeline/pricehistory.py`). No single sales. | **Ruled: both.** Show the sold range on each suggestion, such as "14 sold in 30 days, $3.10 to $4.25". Also plan research into single-sale sources. A separate research lane surveys eBay, PriceCharting and Card Ladder. |
| Drift alerts | `PriceMovers` flags live cards that moved more than 10% since first seen. | **Open.** The owner turned down the first two sets of options. Section 9a rethinks drift from the decision it serves, with a measured count. |
| Net after fees | Nothing. Section 8 leaves out a fee model. | **Ruled: plan it.** Needs the owner's real fee rate. |
| Price many rows at once | Presets on the rule. | **Ruled: plan it.** Select rows, apply one change, preview, confirm. |
| Watch list | A hold watch ("alert when market is above"), printed only by the join report. | **Ruled: plan it.** It grows from the hold watch. |
| Outside signals | Nothing. | **Ruled: plan it.** A reason slot first, for signals like the Riftbound meta research. |
| AI-assisted tools | Nothing for pricing. | **Ruled: candidates to plan.** See section 9b. |

## 9a. Drift alerts: what decision they serve

The owner turned down four drift options (money at stake, ride the send, a weekly session,
explained moves): none was well thought out. Rethought from the outcome: a drift alert helps
one decision, "should this live price change now?". A measured count over the owner's store
answers which way it changes. Of 832 live listings with an asking price and a market price:

| Direction | Listings | Dollars, asking price against market, across copies |
|---|---|---|
| Under market by more than 10% (sells too cheap) | 7 | $0.46 |
| Over market by more than 10% (does not sell) | 444 | $3,124 |
| Over market by $5 or more a copy | 11 | $2,845 |

So drift costs nothing by selling too cheap. The cost is listings priced over what buyers pay,
and 11 cards hold most of it. The new options, one decision for the owner:

1. **Cut drift as a tool.** The one list already does the job: a live listing over market
   shows as a suggested cut, and one past the cap or at the value line lands in Needs you. The
   11 cards land on top.
2. **The one list, plus a line on Home.** As option 1, and Home says "11 listings priced $2,845
   over market" with one press to them. It shows only when a card at the value line is past the
   cap.
3. **An expensive-card watch.** Only cards at the value line are watched, on each daily price
   refresh. Each crossing names the card. The rest wait for the list.

The pick is option 1. Some of the 11 may be held on purpose; the count cannot tell.

## 9c. The floating history card

The owner picked the floating card over the sheet, the row that opens in place and the side
panel, and asked that it open by itself when a price field takes focus. Mockup:
`docs/design/pricing-suggest/history-float.html`.

- **It opens on focus.** A price field taking focus, by press or by Tab, opens the card for that
  row. The history door opens it too.
- **It follows the focused row.** Tabbing down the list moves the card to each row in turn. Nothing
  in the list moves (D313, nothing moves unless the person moved it).
- **It never covers the focused row or the next price field.** Opened by focus, it sits above the
  row, over rows already priced. Where there is no room above, it opens below and clear of the
  price column.
- **Focus stays in the field.** A card opened by focus takes no focus, so Tab goes on to the next
  price. A card opened by the door takes focus and gives it back to the door when it closes.
- **It closes** on Esc (focus stays in the field), on its close button, and when focus leaves the
  list's price fields for anything but the card.
- **It holds its size from its first paint** while the history loads.

## 9b. AI-assisted candidates

Never guess a price (CLAUDE.md, hard rules). Each candidate gives evidence or a preview. None
sets a price without the owner's press.

- **Why it moved.** Section 9a, option 4.
- **Plain-words bulk change.** The owner types "lower every Riftbound common under $1 by 10%".
  The tool shows the rows and the dollar change, and the owner confirms.
- **Near matches for a card with no market price.** It lists sales of the closest printings
  as evidence in Needs you. The owner types the price.
- **A weekly pricing note.** One paragraph: what moved, what sold, what sits.
