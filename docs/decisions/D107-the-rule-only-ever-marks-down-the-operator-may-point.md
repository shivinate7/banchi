## D107 — The rule only ever marks down; the operator may point either way

**A price the operator types goes through in either direction. The automatic rule still cannot propose a raise.** Built 2026-09-06 on the owner's instruction — asked what a raise was *for*, they said the honest thing: *"i just feel like it's a no brainer to have."* That is an argument for symmetry rather than for a scenario, and this entry is scoped to it.

### What was actually wrong

`#/pricing` draws a price field on every live row and lets the operator type into it. `reprice apply` then refused the whole file if any typed price was above the live one — reason `raised`, listed as **fatal** beside a duplicate SKU. So the screen offered a control it would not honour, and the refusal blamed the direction rather than the design.

It was found by a test rather than a review, and by the awkward end of one: **$750 was chosen as a deliberately absurd value precisely because a raise is the SAFE direction to test in** — nobody accidentally buys a $750 common — and the pipeline refused it. The safe direction to experiment in was the one the feature could not do.

### The asymmetry that stays

**`plan` still refuses its own proposal when it is not a markdown** (`NOT_A_MARKDOWN`), and that is not an oversight left standing. The rule is a *markdown* rule: it ranks by staleness, it cuts by a percentage, and every term in it is about stock that is not moving. A rule that could propose upward would need a different trigger — market movement, not age — and that is a different command, not a flag.

**So a price above `was` reaching `read_back` is necessarily one a person typed.** Nothing automatic can produce one. That is what makes letting it through safe, and it is an argument from the code rather than from intent.

### What D100 actually protects, and why direction is not part of it

Three things, none of which depend on which way the price moved:

- **`Add to Quantity` is 0 on every row of every file this path writes.** The quantity is not a variable here; asserted five times, and now a sixth over a raised row.
- **Nothing is deleted at TCGplayer.** `TCG Marketplace Price` edits the live listing in place.
- **A duplicate SKU is still fatal**, because it is undefined behaviour in an import (D7). `Application.fatal` now holds that alone.

**D100's "safe to upload by accident" argument survives and points this way.** A file uploaded by mistake that RAISES costs sales until somebody notices; one that LOWERS sells real stock at the wrong price and cannot be recalled. The direction that was refused is the less dangerous of the two.

### A raise is never silent, and the money figure does not net

`Application.raised` and `taken_on` sit beside `lowered` and `given_up`, and both the preview and `receipt.txt` name the count and the amount on their own line, with a `^` on the row. A row pointing up inside a thing called a markdown is the one an operator most needs told about.

**`given_up` counts reductions only.** It answers *"what does pressing this cost me"*, and letting a raise offset a markdown would report a file that cuts $40 and lifts $40 as free — the one reading an operator must not be given about their own money.

### What this amends

**D100's "this path only lowers"**, which was true of the rule and was being enforced against the human. The rule half is unchanged. `RAISED` stays in the vocabulary because receipts written before today carry it and `reason_label` is what renders them — a code is retired as a refusal without being deleted as a word.

### What would reopen this

*A rule that proposes raises* — repricing to market after a spike, which wants a market-movement trigger and is a sibling command rather than a flag on this one; the owner has named no such need yet. *A raise ceiling*, if a typo ever sends a $2 card to $2,000 — TCGplayer's own validator caps at 200,000 and `server/tcg_import.py` enforces that, but nothing here asks "is this raise plausible". *An operator who wants the sheet renamed*, since "Mark down what is not selling" is now the primary case rather than the only one.
