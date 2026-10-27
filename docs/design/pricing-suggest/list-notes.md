# Pricing by suggestion: notes on the list mockup

Mockup: `list.html` in this folder. Spec: `docs/specs/pricing-suggest.md`. Its section 1 rulings
are the owner's and stay closed. Each option below has a press in the mockup's cull strip that
hides it (`#hide=<key>`).

1. **Market moved trigger** (`moved`). Reason: "Market up 18% since listed." Gain: the most
   direct answer to "old listings drift and nothing says so". Loss: it needs the market on the
   listing day, which the archive holds only after a sweep press. Pick: keep. Owner word: yes.
2. **Unsold N days trigger** (`unsold`). Reason: "Unsold 34 days." Gain: it is today's Live tab
   mark-down, folded into the one list. Loss: it says nothing about the market, so it can lower
   a card that is priced right. Pick: keep, and suggest only a fall. Owner word: yes.
3. **Undercut by others trigger** (`undercut`). Reason: "Others list it from $5.49 shipped,
   under your $6.25." Gain: Low With Shipping is stored and read by no rule now. Loss: one
   low seller can pull a price down. Pick: keep. Owner word: yes.
4. **Selling fast trigger** (`fast`). Reason: "Selling fast: 212 sold across TCGplayer in 30
   days." Gain: the one trigger that raises a price on demand. Loss: it reads market demand, not
   this listing's sales, and a held unlisted card gets no daily read. Pick: keep, as a raise
   only. Owner word: yes.
5. **Outside signal slot** (`signal`). Reason: "Played in a winning deck this week." Gain: room
   for research from another session. Loss: no source exists yet. Pick: a placeholder only;
   build nothing until a source exists. Owner word: yes.
6. **Suggestion limit** (`cap`). The mockup shows 25% either way, a placeholder figure. A move
   inside it sits ticked in Suggested changes. A bigger move sits in Needs you, unticked. Gain:
   one press can never move a price far. Loss: one more number to set. Pick: the owner sets the
   figure. Owner word: yes.
7. **Value line** (`value`). The mockup shows $25.00, a placeholder figure. A card at or above
   it sits in Needs you, unticked. Gain: a costly card never goes without a look. Loss: one
   more number to set. Pick: the owner sets the figure. Owner word: yes.
8. **Needs-you rows start unticked.** Gain: nothing in Needs you goes by accident. Loss: a
   value-line card at the rule price needs one extra press. Pick: unticked. Owner word: yes.
9. **Raises.** Market moved and Selling fast can raise a live price. This reopens D107 (only the
   rule never proposes a raise). The suggestion limit is the raise ceiling D107 asks for. Pick:
   allow raises. Owner word: yes.
10. **PriceMovers block.** The mockup does not draw it. Its read becomes the market moved rows.
    Gain: one place for one fact. Loss: the summary line "N items moved more than 10%" goes.
    Pick: remove the block. Owner word: yes.
11. **Hold word.** The lock's label is "Keep off TCGplayer", a working name. It must differ
    from the send guard's "held back" (spec section 6). Pick: "Keep off TCGplayer". Owner word: yes.
12. **One Send press, three parts.** The bar counts new copies (with their total), kept
    suggestions (up, down, and the net dollar change) and typed prices. A tick changes the count
    at once. Gain: the press says what it does before it runs. Loss: a net change near zero can
    hide two large moves; the up and down counts show them. Pick: as drawn.
13. **Price source chip.** Each row says Rule, You, Floor or Suggested. A row with no price says
    "No price yet". At 820 the chip sits under the price field. Pick: as drawn.
14. **History door.** Each row has a chart button that opens the product sheet, the same place
    the name link opens today. Gain: a visible door for one press. Loss: one more 40px column.
    Pick: as drawn.
15. **Rule wording.** "Market less 5%" is a sample. The anchor waits on the measurement in spec
    section 5. "Floor" replaces "cut-off" on every screen string. Pick: as drawn.
