# Pricing by suggestion: one list, one rule, you confirm

**STATUS: DIRECTION CHOSEN. NOT BUILT.** The owner picked this direction in a pricing ideation
session. The one-list mockup is drawn: `docs/design/pricing-suggest/list.html`, with its notes
and renders at 1440 and 820, light and dark. Section 4b judges each trigger. No build starts
until the owner signs off the mockup.

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
- A suggestion may raise a price. That reopens D107 (a typed price goes either direction, and only
  the rule never proposes a raise). D107 already names this reopener: a market-movement rule. D107 also asks for a raise
  ceiling, and the cap in section 1 is it.
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

A read-only count over the owner's store, from the main checkout. No network, no spend. The
store held 914 live listings. Our asking price is known for 433 of them, and a live market
reading for 498. Thresholds here are samples for the count, not proposals.

| Trigger | Sample threshold | Fires on | Out of |
|---|---|---|---|
| Market moved | 10% / 15% / 25% from listing day | 307 / 233 / 140 | about 500 with a reading and a history |
| Unsold for N days | 14 / 30 / 60 days | 901 / 745 / 0 | 914 |
| Undercut by others | Low With Shipping 5% / 10% / 20% under ours | 5 / 4 / 4 | 254 with both prices |
| Selling fast | 5 / 10 / 30 units sold market-wide in 30 days, ours under market | 3 / 3 / 3 | 433 |
| Past a 25% cap | market more than 25% from our asking price | 193 | 433 |

Two facts shape these numbers. The listings arrived in two waves, so most share one age, and
the median listing is 30 days old. And `sold_here` reads 0 on every live listing, so "unsold"
here is an upper bound: a build must read the order ledger instead.

## 4b. Judgment of each trigger

The owner rules on each from the mockups (`docs/design/pricing-suggest/list.html`). These are the
recommendations.

- **Market moved: keep, as the main trigger.** It is the one signal with volume and meaning.
  At 15% it fires on about half the listings with data, so the cap matters: 140 move more than
  25% and land in Needs you. Each row says the direction and the sold range behind it.
- **Unsold for N days: do not keep alone.** By age alone it fires on 745 of 914 at 30 days and
  none at 60, because the waves share an age. It says "time passed", not "price is wrong". Keep
  it as a qualifier: unsold N days AND our price above market. Then it names a real lowering.
- **Undercut by others: keep, quiet.** It fires on 4 of 254. Low With Shipping is already
  stored. It is cheap and rare, so it adds little noise. The row must say the price includes
  shipping.
- **Selling fast: fold into market moved.** It fires on 3. Its data is market-wide demand, not
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
3. **Name the cap and the value line.** The owner sets both numbers on the mockup.
4. **Reopen decisions on the owner's word**: D107 (only the rule never raises), D105
   (mark-downs live where prices are decided), and D277 (pricing lists all rows) answer Q6, the
   Live tab. D103 (staleness filters, never gates) stands.

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

## 9. More tools: open questions

The owner asked for "more tools at hand". Several exist already. These questions wait on the
owner's word.

| Tool | What exists | What is missing | Recommendation |
|---|---|---|---|
| Price history | A trend line on each row (`PriceTrend`). The full chart on the product sheet, one press away (D278, one product view, two frames). | Nothing on the list itself beyond the trend line. | Keep the sheet. A row that grows in place breaks D313 (nothing moves unless the person moved it). |
| Comparable sales | Per period: copies sold, sale count, lowest and highest sale price (`pipeline/pricehistory.py`). | Single sales. The source never gives "what the last three sold for". | Show the sold range on each suggestion, such as "14 sold in 30 days, $3.10 to $4.25". |
| Drift alerts | `PriceMovers` flags live cards that moved more than 10% since first seen. | It is a read you open, not a prompt to act. | Fold it into the market-moved suggestion. A Home count or a notification is the owner's call. |
| Net after fees | Nothing. Section 8 leaves out a fee model. | The owner's real fee rate. | Open. |
| Price many rows at once | Presets on the rule. | A select-and-apply over chosen rows. | Open. |
| Outside signals | Nothing. | A reason slot only. | Keep the slot in the mockup. Build nothing. |
