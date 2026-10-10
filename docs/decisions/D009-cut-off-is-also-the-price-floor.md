## D9 — Cut-off is also the price floor

**The store's cut-off (`policy.threshold`, default `pipeline/corpus.py:DEFAULT_CUTOFF`, $0.49) is one figure in three roles.** **It is the market price at or above which a card earns a listing.** **It is the price the sub-threshold half goes out at.** **It is the price no rule or markdown may go below.** It derives from the $60/hr labor bar. A marginal pull takes about 20 seconds. A sale under the bar loses money.

There is no `policy.floor`. A second figure can only be set wrong. The pair came apart the first day a cut-off went under the constant. 293 of 354 rows were refused as `below_floor`, and 49 SKUs were written to `import.csv`. `pipeline/pricing.py:FLOOR` is only the no-store default and the labor bar the warnings name. A store that sets a cut-off below it is told once and never refused.

The sub-threshold answer is a store-wide policy with a default (`policy.sub_threshold`, flat at the cut-off), never a per-run choice. An answer never silently tracks a moving floor. An unset answer takes the store default, which is distinct from a chosen $0.49. A stored `"floor"` becomes a flat price on its first edit.

A blank or $0.00 market price is `no_market_data`, never sub-threshold. A missing price is unknown, not low, so it gets no disposition. It is priced by hand or left unlisted, and `emit` refuses while one is unanswered. Without this rule a $40 chase card goes out at the floor because its market cell was empty.

The join keeps the sub-threshold distribution in bands. The bands are cut as fractions of the threshold. A $0.38 rare and a $0.01 code card stay distinct before a bulk lot is chosen. TCGplayer's Bulk Lots category is the exit for what is not listed.
