## DEBT-read-budget-miss-paths — The read-budget check proves some routes on their miss path only

**`harness/tests/t7/read_budget.py` budgets about 15 routes against a fixture that never reaches their hit path.** A per-card walk added to one of them stays green.

- **404 or 409 here:** a box by name, markdown stamps, a send file, run history, the review catalog, product history, and a shipping file.
- **Never exercised:** markdowns, sends and shipping batches. Every fixture order is open, where real stores hold most orders fulfilled.
- **Not counted:** work done by file reads, not SQL. Examples: product realized, run scope, saved trends and photo by card.
- **Not fixed because** each needs fixture records the harness does not build yet. The check's status row catches a hit path that turns into a miss, not the reverse.
- **Closes when** the fixture builds a markdown, a send, a shipping batch and a mix of fulfilled orders. Each route above then gets a budget row on its 200 path.

**Outcome at risk.** One of these screens gets slower as the store grows, and no check fails.
