# Pricing, one question at a time: design notes

Designer kind: directed. Direction: one question at a time. The screen opens on the next price
that needs the owner, and the full table is a second view. Mockup: `pricing-directed-1.html`.
Specs: `docs/specs/pricing-suggest.md`, `docs/specs/stale-listings.md`. Debts: DEBT89 (the send
bar vanishes with zero runs or a failed load), DEBT90 (a send notice lands late), DEBT91 (the
send press widens). Every card, name and figure on the page is made up.

Deep links (add `&w=820`, `&t=dark`, `&t=abyssal-bloom` or `&t=carnival-midway`, `&tags=off`,
`&hide=rail,chart,batch,keys,what,skip`): `#s=q` (add `&q=2` to `&q=9`), `#s=fall`,
`#s=nomarket`, `#s=value`, `#s=typed`, `#s=hold`, `#s=batch`, `#s=done`, `#s=allwell`, `#s=none`,
`#s=loading`, `#s=failed`, `#s=notes`, `#s=settings`, `#s=review`, `#s=sending`, `#s=sent`,
`#s=table`, `#s=detail`, `#s=filtered`. With no `t`, the page follows `prefers-color-scheme`.
Every press works: the keys, the answers, the hold, skip, back, the queue, the view switch, the
sheets and the send. The hash follows each press.

1. **Questions first, the table second.** Pricing opens on the next question. A view switch
   reads "Questions 9" and "All prices 1,110". Gain: the first price that needs the owner is the
   first thing on screen; today about nine status lines stand above row 1 of 1,110. Loss: the
   whole list is one press away, not under the bar. Pick: questions first. Departs from: spec
   pricing-suggest section 1 ("One list, groups on top", signed off) and D277 (Pricing lists all
   rows). Owner grant: yes.
2. **Which questions.** The Needs you group (spec section 3): a move past the limit, no market
   price, a card at or above the value line. The suggestions inside the limit come last as one
   question (item 10). Going at the rule asks nothing. Pick: as drawn.
3. **Order: most money first.** Copies times the price move, or the price for a new copy. The
   order is taken once at load and holds (ux-order-holds-still). Gain: the costly mistakes come
   while attention is fresh. Loss: cards of one set no longer sit together. Departs from: today's
   arranged order in Needs you (`Pricing.tsx` `Pricing`, the `arranged` sort). Not blocking.
4. **The question card.** One sentence asks (the one large type on the page), one line says why,
   four facts (your price now, market, lowest shipped, sold in 30 days), the photo, and a 90-day
   chart with market, your price since listed and the suggestion dot (today's
   `HistoryFloat.tsx` chart, inline). Option `chart` hides the chart; then the history door
   opens the floating card as today. Pick: chart in the card.
5. **Answers are prices.** Each answer is one press with its price on it: the suggestion
   (Enter), Market (M), Lowest, shipped (L), No change (N, live listings only), or a typed price
   (any digit jumps to the field, Enter uses it). Hold back (H), Skip for now (S), Back (U). M,
   L, H and U are today's keys (`Pricing.tsx` `SNAPS` and `onKey`). Enter, N and S are new:
   today Enter commits the field and moves down. Option `keys` hides the key caps. Pick: keys on.
6. **The answer shows at the press.** The chosen answer turns green with a check, the line under
   it says "Raised to $1.24.", and the next question takes the slot 650 ms later (250 ms with
   reduced motion). Nothing else moves (ux-answer-at-press, D313).
7. **Hold back, in the card.** The answers give way to today's hold: Bullish (B), Keep off
   TCGplayer (K), A later batch (X), "Alert when market is above", Note, Cancel, "Keep it off"
   (`Pricing.tsx` `HoldPanel`, `holds.ts`). Gain: no popover over the next rows. Loss: none seen.
8. **Skip for now.** A skipped question goes to the end of Up next, marked Skipped. Nothing
   unanswered goes. The done state offers "Answer the skipped". Option `skip`. Pick: keep it.
9. **The queue beside the card.** Up next and Answered, each a press that opens that question,
   so any answer can change before the send. At 820 it folds under the card in two columns.
   The key list sits under it at 1440. Option `rail`. Pick: keep it.
10. **Suggestions inside the limit, asked once.** "24 listings move inside your 25% limit. Send
    them with the rest?" Answers: Send them (they are ticked already, spec section 3), Look at
    each one (opens All prices on Suggested), Leave them out (unticks all 24). Option `batch`.
    Pick: keep it. Owner grant: yes (Leave them out is a new mass untick; ticks are kept per
    the spec's `POST /pricing/ticks`).
11. **The send bar holds still.** One height (72px) and one press width (228px at 1440, 188px at
    820) from first paint. Loading, failed, nothing yet, ready, sending and the receipt each
    draw in the same one-line slot, so nothing joins the bar later. Closes DEBT89, DEBT90 and
    DEBT91 by construction. Loss: a receipt with a list (left out, turned away) shows its
    sentence in the slot and its list in the What goes sheet. Pick: as drawn.
12. **One unit: copies.** "64 copies ready", "Send 64 copies", and every count in the What goes
    sheet. Gain: one count, one unit. Departs from: the press label "Send All N SKUs, M Live
    Copies Move to New Prices" (`SendCard.tsx` `SendCard`). Home's "18 ready" (`standing.ts`)
    also needs copies, outside this screen. Owner grant: yes (Home wording).
13. **What goes (today's "Show 92 Live Copies" fold).** A sheet: new listings, prices up, prices
    down, your typed prices, each with copies and money and a fold that names the cards; then
    kept off and questions not answered. Its Send press is the same act as the bar's (D273, one
    press sends, holds from the bar). Option `what`. At 820 the bar shows it as an icon.
14. **Status lines fold into one chip.** "Prices read today at 7:02" and Refresh stay
    (`PricesAsOf.tsx`). The not-normal lines (no daily read, no overnight trends read, readings
    not matched) go in a "2 notes" chip that opens a list. With none it reads "All is well."
    (ux-all-is-well). Rule, floor, limit and value line move to "Your rules", a sheet
    (`Pricing.tsx` `RuleSheet`). The PriceMovers block is not drawn: its read is the market
    moved questions. Owner grant: yes (spec section 9a, PriceMovers, not ruled).
15. **All prices pages its rows.** The signed-off one list (`pricing-suggest/list.html`) with
    group chips and counts. Each group shows 50 rows and "Show the next 50". Gain: the page is
    no longer about 122,000px tall at 820. Loss: the browser's find covers only shown rows; the
    search covers all. Departs from: D277 (all rows). Owner grant: yes.
16. **A row opens the question card.** In All prices, the name or the history door opens the same
    card in a sheet, with its answers. One home for a row's detail. Departs from: spec section
    9c, the floating history card above the row (signed off). Owner grant: yes.
17. **Empty and end states** (ux-unknown-is-not-empty): every question answered (`#s=done`),
    nothing needs you at load (`#s=allwell`), no copies yet with Go to Capture (`#s=none`), a
    failed read with Read it again and a closed "What the server said" (`#s=failed`), loading
    at the loaded size (`#s=loading`), a search that empties the table with Clear the search
    (`#s=filtered`).
18. **Receipt words are today's.** "68 copies went live at 9:14. Banchi checks TCGplayer again
    after 9:44." (`SendCard.tsx` `SendStanding`, the waiting case). The other receipts (sending,
    unknown, written, short, turned away) take the same slot. Take back joins the slot's press
    when the server says the copies are takeable; it is not drawn.

Sizes and themes: 1440 and 820, light and dark, and the two palettes through `t=`. Tokens are
`app/src/tokens.css`, inlined. Fonts link `app/src/fonts.css` from this checkout.
