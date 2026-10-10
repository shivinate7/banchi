## D107 — Typed price goes either direction

**A price the operator types goes through raised or lowered.** Only the automatic rule never proposes a raise. `reprice apply` once refused the whole file if any typed price exceeded the live one (`raised`, fatal beside a duplicate SKU), so the screen offered a field it would not honor.

- **The asymmetry that stays.** `plan` still refuses its own non-markdown proposals (`NOT_A_MARKDOWN`). The rule ranks by staleness and cuts by a percentage. So a rule that raised would need a market-movement trigger and is a sibling command, not a flag. So a price above `was` reaching `read_back` is necessarily typed, which is what makes letting it through safe.
- **D100 protects three things, and none depends on direction.** `Add to Quantity` is 0 on every row of every file this path writes. Nothing is deleted at TCGplayer, since `TCG Marketplace Price` edits the listing in place. A duplicate SKU is fatal (D7), and `Application.fatal` holds that alone. A file uploaded by mistake that raises costs sales until noticed. By contrast, a file that lowers sells real stock at the wrong price and cannot be recalled.
- **A raise is never silent, and the money figure does not net.** `Application.raised` and `taken_on` sit beside `lowered` and `given_up`. The preview and `receipt.txt` name the count and amount on their own line, with a `^` on the row. `given_up` counts reductions only, so a file that cuts $40 and lifts $40 is not reported as free.
- **`RAISED` stays in the vocabulary** for receipts written before, and `reason_label` renders it. A code is retired as a refusal without being deleted as a word.

Reopen for a rule that proposes raises (a market-movement command), or for a raise ceiling if a typo sends a $2 card to $2,000. TCGplayer's own validator caps at 200,000 and `server/tcg_import.py` enforces it, but nothing asks whether a raise is plausible.
