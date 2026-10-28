# D324 — Banchi values the owner's investment holdings, then flags big lines on price signals

Banchi values the owner's investment holdings at its own prices, then flags lines of $100 or more a unit when a price signal fires.

Kind: process
Home: D324

**The owner ruled it** (waiting-page item 20). The mailaudit purchase roster is the owner's
investment buys, held outside Banchi's scan-and-list flow. Banchi values those holdings at its own
prices, then flags lines of $100 or more a unit when a price-pattern signal fires. No seller or
buyer names, and none of mailaudit's ledger, enter Banchi. Output is totals and product ids.

**Why.** Measured on the latest OrderWand export (non-canceled TCG purchases): 1,175 units, $65.6k
paid. 117 lines at $100 or more a unit hold $44.5k (68%). Banchi prices 376 of 893 lines by exact
name (521 units): $32.2k paid, $34.2k at market (+6%, rough: no printing or condition match).
Sealed: 38 of 66 lines priced.

**Boundaries.** The export's sale rows are Banchi's own orders (892 of 892), so they do not net out
sales of the investment buys. Those sales need the owner's TCGplayer sales export (waiting-page
item 21); without it the report is labeled "units sold unknown". The join is set plus normalized
product name against Banchi SKUs; the roster has no collector numbers, so the number key does not
apply.

**Order of work.** First a one-off, read-only value report: per product id, units held, paid,
market now and gain, with a coverage line. Then the sell-signal flags, only once the price-pattern
signals are on main and the brief names the signal and its measured false-alarm rate.

**Reopen** if the investment buys move into the scan-and-list flow, or a better join than names
appears.
