## DEBT69 — prices are not refreshed on a schedule, and nothing says which SKUs moved

**Gap.** `fetch(Scope(...))` on a cron could store a dated export so a pricing decision meets today's market. The safe half is to show which SKUs moved more than 10% since listing, on `#/pricing`, and leave the decision to a person.

**Not this debt.** An automatic push of new live prices needs its own decision entry. It takes the shape of a free preflight that shows each change, then a confirm that is not a default. An unattended loop that moves live prices is the one thing here that can lose money unseen.
