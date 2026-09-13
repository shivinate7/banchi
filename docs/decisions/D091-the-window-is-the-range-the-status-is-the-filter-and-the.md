## D91 — The window is the range, the status is the filter, and the operator picks it from what the wire returned

**The order fetch is two presses: the search pages are walked whole and counted by the status string TCGplayer gave each order, and only the statuses the operator ticks are detailed.** Built 2026-09-02, after the owner reported that the fetch had never worked once on the account it exists for. The refusal, verbatim: *"The LastThreeMonths range holds 370 orders and this fetch is capped at 100. Nothing was read rather than the first 100 being read and the rest silently left behind. Ask for a narrower range."* Code `order_too_many`.

**The cap was on the wrong quantity, and the remedy it printed could not be followed.** `server/order_transport.py` capped the ORDERS IN THE WINDOW at 100 to keep one press inside the only request budget anyone has a number for. A fetch is one search page per 25 orders plus one detail request per order, and `MAX_ORDERS` sized the whole of that against the 120 requests a minute the bridge extension holds itself to — a figure that is that client's own self-limit, read out of its source, and not a measurement of TCGplayer's server. The window's size is not what spends the budget: the pages are cheap and the details are the cost. And "ask for a narrower range" names a thing the transport cannot do — `Custom` needs a date pair whose query string was never captured, and the two ranges it knows are three months and two years.

### What the press measured

| | |
|---|---|
| orders in `LastThreeMonths`, this account, 2026-09-02 | **370** |
| the cap the fetch refused at | 100 |
| search pages to walk the whole window | 15 |
| requests for a full detail of the window | 385 |
| requests for the two orders awaiting shipment (D87's `Ready to Ship`) | 17 |
| times the one-press fetch had returned an order | **0** |

**The first row is the first real number this repo has about the order feed's size**, and it retires the "347 orders in 90 days" that `docs/specs/order-pipeline.md` §6 carried as an unverified external figure. The last row is the finding: a guard sized to protect the budget had made the route unusable on the one account it serves, and nothing in the tree could see that, because no test of `do_order_fetch` existed and no fixture holds 370 of anything.

### The status is the operator's and never the code's

**`fetch_open_orders`' own docstring ruled that "open" is the range and not a status filter, because the status vocabulary was never enumerated on the wire, and that ruling stands.** A string this module decided meant "still needs picking" would be a guess, and a guess that drops an order is an envelope that never ships. What changed is who chooses. `POST /orders/fetch {preview: true}` walks the summaries — `order_transport.summaries`, one request per 25 orders, no detail call — and answers the window counted by the status STRING each order carried, verbatim, with how many of each the ledger already holds at that status. The screen draws those strings as rows with tick boxes and nothing pre-ticked. `POST /orders/fetch {statuses: [...]}` details only the ticked ones, compared verbatim after a strip: never folded, never mapped, never a constant in code. The strings on the wire are the strings on the screen, and the operator ticks the two they are about to put in envelopes rather than the 280 that already shipped.

**The cap moved to the detail calls and it stays.** Fifteen pages plus a hundred details is 115 requests, inside the budget; a two-year window would not be, and its page count is what would reopen this. Past the cap the rest is COUNTED and answered as `remaining`, never silently left behind — `CLAUDE.md`'s rule against a silent drop is kept by making the drop loud and finite — and the next press picks it up, because `skip_known` hands the transport `{number: status}` as the ledger holds them and an order already detailed at this status is not detailed twice. An order whose status moved IS detailed again, which is how a shipped order's new word reaches the ledger without a full re-fetch. That map is `_known_orders`, read out of a store snapshot; the route still writes nothing.

**The transport does not sleep.** A route that paused its way through 370 details to stay under the budget would block one HTTP request for minutes, which is the wrong shape for a button and the shape D33 spawns a child for. Two presses inside one minute can pass the budget and nothing stops them; that is a cost named below rather than a cooldown, because the owner's ruling for this work was that the fetch stays a press and everything after it is what gets automated.

### What it costs

**Two presses where there was one, and a table to read between them.** The first press is the price of not guessing at the vocabulary. **The status strings are TCGplayer's, seen once.** The filter and the delta both compare the summary's `orderStatus` against the ledger's stored `status`, which came from the detail; if the two endpoints ever spell one state differently, `skip_known` re-details that order on every press. The preview would show the doubled string, so the operator would see it. **The `Custom` range is still not captured**, so the window is three months or two years and nothing between. **No cooldown**: the budget is the operator's to respect across presses. **And `detail` is still unexercised against the live host** — the summary walk is proven by the very refusal that opened this entry, and the projection of a buyer's name and address is proven against fixtures only. The first filtered fetch the owner presses is the measurement, and the transport's STATUS block says so.

**AMENDED 2026-09-13 (`D-the-ledger-names-the-buyer`): `{all_statuses: true}` is now the explicit "every one" this refusal always allowed for.** `statuses_required` never demanded a
NARROW list, only that the caller say what it means rather than have the transport guess; a
one-time two-year backfill means literally every status, and naming that in words is not the
guess this entry refuses. `do_order_fetch` still refuses a call naming neither `statuses` nor
`all_statuses`, and now also one naming both.

**What would reopen this: a status spelled two ways between the summary and the detail, `Custom` captured off the wire, or orders arriving faster than a person presses.** The first is the delta re-detailing an order every press; the second gives the window a date and makes the status table smaller; the third is an unattended fetch, which is its own entry with its own argument about a cookie that expires under D53's supervisor with nobody watching the refusal.
