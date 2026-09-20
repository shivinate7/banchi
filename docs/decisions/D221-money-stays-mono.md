## D221 — Money stays mono, and the rule is amended to match

**The owner's ruling, 2026-09-19: mono is a font, and money in a table keeps it.**

### The contradiction

CLAUDE.md's type paragraph read: "Numbers in tables are Inter tabular-nums, not mono."
`app/src/kit.css:123` defines `.bn-money` as mono, 600 weight, tabular figures, the money
colour. Ten files use it, including table cells in `Revenue.tsx` and `Pricing.css`.
`app/src/RunPanel.tsx:223` carries a comment defending exactly that treatment: ".bn-money is
mono, 600 and tabular — the treatment a column of dollar amounts needs." The rule and the
primitive have disagreed for as long as both have existed.

### Both sides

The rule's argument was that `--bn-font-mono` (JetBrains Mono) SIGNALS a machine string — a
SKU, a run name, a reason code, a card number. Money in a table is a quantity a person reads.
It is not a string a machine emits. So the argument went, it should sit with every other
number in Inter tabular-nums.

The primitive's argument is `.bn-money` itself: built, shipped, and never changed since.
Money is a figure the whole store measures itself by. The front page's ranked line,
Pricing's worklist, and Revenue's totals all agree on the mono face already. Mono at 600
weight reads as a fixed-width ledger figure, heavier than a plain quantity. Every screen
showing money already agrees with each other, not with the rule.

The owner asked whether mono was just a font. It is. Both treatments align a column equally
well — `font-variant-numeric: tabular-nums` does that on either face. Alignment never
decided this. The owner judged the signal argument not worth the contradiction, and ruled
for the primitive.

### What changes, and what does not

CLAUDE.md's type paragraph now names money as one exception. Numbers in tables are still
Inter tabular-nums. Money alone takes the mono face, through `.bn-money`, and never through a
hand-rolled declaration that copies its look. Every other table figure — a bare count, a
quantity, an index, a percentage — keeps the old rule exactly as it read.

No styling changed. `.bn-money` already did what the amended rule now describes.
`app/src/RunPanel.tsx:226`'s comment already argued the correct side. It needed no edit.

### Mechanization

D173: a rule that can be enforced mechanically must be. **NOT MECHANIZED:** a machine cannot
tell a dollar figure from another tabular machine string by its CSS alone. `app/src` already
carries dozens of legitimate `font-family: var(--bn-font-mono)` declarations. They share the
same 600 weight and the same tabular figures. SKUs, run ids, box addresses and card numbers
all use the same combination — `ReviewQueue.css`'s `.review-value` and `OrdersWalk.css`'s
`.walkplan-address-num` are two of many. Telling "this span is money" from "this span is
another machine string" needs the data the span renders, not the declaration that styles it.
No static reader carries that.

One narrower signature was considered and rejected as a false promise: flagging any selector
outside `.bn-money` that combines `var(--bn-font-mono)` with `var(--bn-money)`'s colour
token. That would catch a literal copy of `.bn-money`'s four properties. It would not catch a
hand-rolled treatment that reuses mono and tabular figures with any other text colour.
`ReviewQueue.css:463` and `Pricing.css:112` already show that exact shape for non-money mono
text. A reader built to that signature would pass real violations and print `ok`. That is
worse than the admission above.

### Governed by

The type paragraph itself, CLAUDE.md's "Type has three roles" sentence, carries the same
`**NOT MECHANIZED:**` admission inline. D173 requires a rule to name its enforcement or argue
why none exists.
