## DEBT64 — the collector number is not cross-checked against the local catalog

**Gap.** `routing.NAME_DISPUTED` (D23) already queues a read whose number lands on a real row with a different name. What is left: a number that lands on no row is not cross-checked by name. With a set hint, the catalog yields `(set, name) -> number` and `(set) -> printedTotal` independently of the model, and that could check it.

**Limit.** It converts misses into review taps and buys safety, not a higher T1 score.
