# Pricing by suggestion: notes on the list mockup

Mockup: `list.html` in this folder. Spec: `docs/specs/pricing-suggest.md`. Its section 1 rulings
are the owner's and stay closed. Section 4b gives a recommendation for each trigger. The owner
has ruled on none yet. Each option has a press in the mockup's cull strip that hides it
(`#hide=<key>`).

"Owner word: yes" marks a question that is still open. "Pick" is the designer's recommendation,
not a ruling.

1. **Market moved** (`moved`). The main trigger. Each row says the direction and the change
   since listed: "Market up 18% since listed." Gain: it is the one signal with volume and
   meaning. Loss: it needs the market on the listing day. Pick: keep. Owner word: yes. Open:
   keep market moved as the main trigger?
2. **Units sold, as evidence** (`fast`). Selling fast is not its own trigger. Its market-wide
   units sold and the sold range follow a market-moved reason: "14 sold on TCGplayer in 30 days,
   $3.10 to $4.25." Gain: the reason shows what stands behind it. Loss: the line is longer, and
   the units are market-wide, not this listing's sales. Pick: show it. Owner word: yes. Open:
   show units sold and the range on market-moved rows?
3. **Unsold and above market** (`unsold`). It fires only when both hold: "Unsold 34 days, and
   $0.11 above market." Days alone never fire it. Gain: it names a real lowering. Loss: it fires
   less often than age alone. Pick: keep as a qualifier. Owner word: yes. Open: keep unsold N
   days only with "above market"? Which N?
4. **Undercut by others** (`undercut`). "Others list it from $5.49 with shipping, under your
   $6.25." The row says the price includes shipping. Gain: the data is stored already, and it
   is rare. Loss: one low seller can pull a price down. Pick: keep, quiet. Owner word: yes.
   Open: keep undercut?
5. **Outside signal** (`signal`). A slot for a reason from another session's research, such as
   "Played in a winning deck this week." Nothing builds it now. Pick: a placeholder only. Owner
   word: yes. Open: keep the slot in the design?
6. **As first drawn** (`first`). A compare group: unsold by age alone, and selling fast as its own
   trigger. It counts toward no send. Pick: remove it once the owner has compared. Owner word:
   yes. Open: is the comparison done?
7. **Suggestion limit** (`cap`). 25% either way is a placeholder figure. A move inside it sits
   ticked in Suggested changes. A bigger move sits in Needs you, unticked. Owner word: yes. Open:
   what figure?
8. **Value line** (`value`). $25.00 is a placeholder figure. A card at or above it sits in Needs
   you, unticked. Owner word: yes. Open: what figure?
9. **Needs-you rows start unticked.** Gain: nothing in Needs you goes by accident. Loss: a
   value-line card at the rule price needs one more press. Pick: unticked. Owner word: yes.
   Open: start them unticked?
10. **Raises.** Market moved can raise a live price. This reopens D107 (only the rule never
    proposes a raise). The suggestion limit is the raise ceiling D107 asks for. Pick: allow
    raises. Owner word: yes. Open: may a suggestion raise a price?
11. **PriceMovers block.** The mockup does not draw it. Its read becomes the market-moved rows.
    Loss: the summary line "N items moved more than 10%" goes. Pick: remove it. Owner word: yes.
    Open: remove the block?
12. **Hold word.** The lock's label is "Keep off TCGplayer", a working name. It must differ from
    the send guard's "held back" (spec section 6). Owner word: yes. Open: which word?
13. **Send bar.** Sticky under the sample ribbon, so it stays in view. It gives the copies in
    all, the new copies with their listing total, the rises with their total, the falls with
    their total, and the typed prices with their total. A tick changes the figures at once.
    Pick: as drawn.
14. **Price source.** Each row says Rule, You, Floor or Suggested. "You" has its own tone, and a
    typed price field carries today's "your price" check. Pick: as drawn.
15. **Two spans, each labeled.** The trend column covers 30 days ("Trend, 30 days"). A
    market-moved reason covers the time since listing ("since listed"). Pick: as drawn.
16. **Row shape.** The reason runs on its own line under the name and figures, so it fits on one
    line at 1440 and 820. At 820 the references take their own line. The name link is 40px tall.
    Rows and group titles sit on the page's 24px left edge. Pick: as drawn.
17. **History door.** Each row has a chart button that opens the product sheet, the same place
    the name link opens today. Pick: as drawn.
18. **Rule wording.** "Market less 5%" is a sample. The anchor waits on the measurement in spec
    section 5. "Floor" replaces "cut-off" in every screen string. Pick: as drawn.
