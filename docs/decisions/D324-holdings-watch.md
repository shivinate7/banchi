# D324 — Banchi values the owner's investment holdings, then flags big lines on price signals

Banchi values the owner's investment holdings at its own prices, then flags lines of $100 or more a unit when a price signal fires.

Kind: process
Home: D324

**The owner ruled it** (waiting-page item 20). The mailaudit purchase roster is the owner's
investment buys, held outside Banchi's scan-and-list flow. Banchi values those holdings at its own
prices, then flags lines of $100 or more a unit when a price-pattern signal fires. No seller or
buyer names, and none of mailaudit's ledger, enter Banchi. Output is totals and product ids.

**Why.** Measured on the latest OrderWand export (non-canceled TCG purchases): 1,175 units, $65.6k
paid. 117 lines at $100 or more a unit hold $44.5k (68%). The store's price archive carries a
product id for each SKU, and that id reaches 839 of 893 lines. The name join reached 376.

**Boundaries.** The export's sale rows are Banchi's own orders (892 of 892), so they do not net out
sales of the investment buys. Those sales need the owner's TCGplayer sales export (waiting-page
item 21); without it the report is labeled "units sold unknown". The join is the roster's product id against the price
archive's product id (owner, waiting-page item 119). The name join stays as a cross-check: a line it prices that the id join does not is
reported.

**Order of work.** First a one-off, read-only value report: per product id, units held, paid,
market now and gain, with a coverage line. Then the sell-signal flags, only once the price-pattern
signals are on main and the brief names the signal and its measured false-alarm rate.

**Reopen** if the investment buys move into the scan-and-list flow, or the archive's product ids
stop matching the roster's.
