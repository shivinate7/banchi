# Lot Tag at the Feeder: notes

The idea: each capture run carries the purchase it came from (paid, date, seller). Once every card is priced, the cost is spread over the cards (a $0.05 floor plus market-value share); a card with no purchase reads "cost unknown", every total says how much stock it covers, and a purchase page shows paid, back, cards left and break-even.

**Click through.** Open `lot-tag.html`. The State bar reaches every state of the plan's section 2 and the two extra views, each with a link: `#state=new|partway|broke-even|no-lot|split|kept-traded|picker|picker-new|card`. Add `&t=dark` or `&t=light` (none follows the system), `&word=lot`, `&back=net`, `&be=plan`, `&home=nav`, `&hide=proj,bar`, `&labels=off`. Inside the page: each list row opens its purchase, each card row opens its cost line, Mark Capture Done on the split purchase spreads it, and the New Purchase option opens the form. "Choices on This Page" switches or hides each choice below.

**Where it lives.** Reached from Sales (`#/revenue`, `app/src/Revenue.tsx`) as a third tab beside Sales and Mix, like `?lens=mix`; the picker is a new row in Capture setup (`CaptureScreen`, the `.capture-row` list). Nearest spec: `docs/specs/sales-plan.md`, "Plans, not built", Cost basis. Overlap: `docs/specs/sales-screen.md` (gross only, D214, sales shows gross, never profit).

**Choices** (Gain / Lose / Pick)
1. The word on screen is "purchase", with "lot" as a switch. Gain: the repo's own term; "lot" already means code-card lots and bulk lots. Lose: the idea's name and the brief's cost line read "lot". Pick: purchase. Owner grant: yes.
2. Back counts gross sales, labelled "gross, before fees" at each figure. Gain: true with today's order data. Lose: break-even comes early by the fees. "After fees" is the switch. Pick: gross.
3. After break-even the page says "$86 more back than paid", not the plan's "+$86 since". Gain: no profit claim. Lose: less punchy. Pick: gross wording. Owner grant: yes.
4. Coverage sits once, as a meter over the three totals, not repeated under each figure (ux-label-once). Gain: one place to read it. Lose: a total copied alone loses its coverage. Pick: once.
5. The recovery bar, with Paid as a mark and the overflow past it in green, is the one bold element. Gain: break-even reads at a glance. Lose: none found. Pick: yes.
6. The projection ("near March") is drawn but marked New, after v1, since the plan defers it. Pick: hide in v1.
7. Mark Capture Done stays off until every card is priced, and says why. Gain: the spread runs once on full data (plan P3). Pick: yes.
8. The picker keycap is L (P is Product). Pick: L.
9. Old stock is tagged by box and section range, with Undo. "Cost unknown" is a fine end state. Pick: yes.

**Departs from**
- Departs from: sales-plan Cost basis, one cost per purchase, per-card split left open. Here each card gets a share. Owner grant: yes.
- Departs from: sales-plan Cost basis, the cost typed in Capture setup as a sticky claim. Here it is picked from a list in a new row, with a form for a new one.
- Departs from: D214 and sales-screen, Sales shows no cost. A Purchases tab inside Sales adds paid and cost on shelf. It still never says profit. Owner grant: yes.
- Departs from: sales-screen, the order wire drops `transaction`, so no fees reach the browser. "After fees" needs that widened (server, not this folder).

**Owner questions (from the plan)**
1. Is the year-end view for tax filing (then a method change applies only from next year) or for your own insight?
2. Can the ~3,600 cards on hand be traced to purchases by box or section from receipts, or should they stay "cost unknown"?
3. In a trade, do incoming cards cost what the outgoing cards cost you, or the market value of what you gave?
4. Purchase or lot as the word (choice 1)?

**Verdicts.** 1440 light (`lot-tag-1440-light.png`, partway): pass, list and page sit side by side with no overflow. 820 dark (`lot-tag-820-dark.png`, broke-even): pass, the rail shows and the list stacks above the page. Also looked at: picker-new 1440 light, card 1440 dark with `word=lot`, both pass.
