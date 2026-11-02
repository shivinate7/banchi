# Pricing by suggestion: notes on the list mockup

Mockup: `list.html` in this folder. Spec: `docs/specs/pricing-suggest.md`. The owner signed off
the mockup, and the spec's section 1 rulings and section 4b judgments govern it. Each option still
has a press in the mockup's cull strip that hides it (`#hide=<key>`). "Owner grant: yes" marks a
question that is still open. "Pick" is the designer's recommendation, not a ruling.

1. **Market moved** (`moved`). The main trigger. Each row says the direction and the change
   since listed: "Market up 18% since listed." Ruled: keep (spec section 4b).
2. **Units sold, as evidence** (`fast`). Selling fast is not its own trigger. Its market-wide
   units sold and the sold range follow a market-moved reason: "14 sold on TCGplayer in 30 days,
   $3.10 to $4.25." Ruled: show it (spec sections 4b and 9).
3. **Unsold and above market** (`unsold`). It fires only when both hold: "Unsold 34 days, and
   $0.11 above market." Days alone never fire it. Ruled: a qualifier (spec section 4b).
   Owner grant: yes. Open: which N?
4. **Undercut by others** (`undercut`). "Others list it from $5.49 with shipping, under your
   $6.25." The row says the price includes shipping. Ruled: keep, quiet (spec section 4b).
5. **Outside signal** (`signal`). A slot for a reason from outside, such as "Played in a winning
   deck this week." Nothing builds it now (spec section 4b). The sample row is ticked, so it counts
   in the send figures; the builder draws no such row until a signal exists. Owner grant: yes.
   Open: keep the slot in the design?
6. **Suggestion limit** (`cap`). Starts at 25% either way, an owner setting (spec section 5,
   step 3). The tile says "You set it", as the floor does. A move inside it sits ticked in
   Suggested changes. A bigger move sits in Needs you, unticked.
7. **Raises stop at the limit.** A suggestion may raise a price, up to the limit (D107, typed
   price either direction, its Reopened line: the limit is the raise ceiling). A raise past the
   limit is cut to the limit and waits in Needs you: Iono goes $8.80 to $11.00, "Market up 41%
   since listed, capped at your 25%." A fall past the limit keeps its full depth and waits for a
   tick (spec section 1, "a cap both ways"). Owner grant: yes. Open, not blocking: should a fall
   past the limit also stop at the limit?
8. **Value line** (`value`). Starts at $25.00, an owner setting (spec section 5, step 3). A card
   at or above it sits in Needs you, unticked: "Worth $25.00 or more. Check the price before it
   goes."
9. **Needs-you rows start unticked.** Gain: nothing in Needs you goes by accident. Loss: a
   value-line card at the rule price needs one more press. Pick: unticked.
10. **PriceMovers block.** The mockup does not draw it. Its read becomes the market-moved rows.
    Loss: the summary line "N items moved more than 10%" goes. Spec section 9a picks this (option
    1) but the owner has not ruled. Owner grant: yes. Open: remove the block?
11. **Hold words.** The lock's label is "Keep off TCGplayer". A card kept back is "kept off
    TCGplayer". Both are today's words (`Pricing.tsx`, the held tile). They differ from the send
    guard's "held back" (spec section 6).
12. **Kept-off cards.** Today's kept-off tile becomes the send bar's last figure, "2 kept off
    TCGplayer, not in this send", and a filter press, "Show kept off (2)". Kept-off rows are not in
    the three groups. Pick: as drawn.
13. **Send bar.** Sticky under the sample ribbon, so it stays in view. It gives the copies in
    all, the new copies with their listing total, the rises with their total, the falls with
    their total, the typed prices with their total, and the kept-off count. A tick changes the
    figures at once. The press reads "Send 11 copies to TCGplayer". Pick: as drawn.
14. **Price source.** Each row says Rule, You, Floor, Suggested or Live (spec section 2). "You" has
    its own tone, and a typed price field carries today's "your price" check. "Live" marks a live
    listing with no reason to change; it keeps the price it listed at. Pick: as drawn.
15. **Two spans, each labeled.** The trend column covers 30 days ("Trend, 30 days"). A
    market-moved reason covers the time since listing ("since listed"). Pick: as drawn.
16. **Row shape.** The reason runs on its own line under the name and figures, and fits on one
    line at 1440 and 820. At 820 the references take their own line. The name link is 40px tall.
    Rows and group titles sit on the page's 24px left edge. Pick: as drawn.
17. **History door.** Each row has a chart button. The floating history card (spec section 9c)
    replaces the product sheet as its target; `history-float.html` draws it. Pick: as drawn.
18. **Rule wording.** "Market less 5%" is a sample. The anchor is Market (spec section 5, step 1).
    "Floor" replaces "cut-off" in every screen string. Pick: as drawn.

On-screen strings the builder uses:

- Group headings: "Needs you", "Suggested changes", "Going at the rule".
- Value line: the tile "Value line", "$25.00", "A card worth this or more waits for you."; the row
  reason "Worth $25.00 or more. Check the price before it goes."
- Send: "Send N copies to TCGplayer", where N is the count (one copy reads "1 copy").
