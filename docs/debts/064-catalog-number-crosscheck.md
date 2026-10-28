## DEBT64 — the collector number's printed total is not cross-checked against the local catalog

**What.** Two checks cross-check a read's number by name. `routing.NAME_DISPUTED` (D23) queues a read whose number lands on a real row with a different name. The `name?:` rung in `join` (D35) takes a number that lands on no row to the name: a name that resolves to one card is released to the ladder's own verdict and lists unless another reason queues it, and `routing.NUMBER_UNREAD_NAME_MATCHED` queues it only when `join.distinct_cards` of the found rows is above 1. What is left: the number's printed total is not checked. With a set hint, the catalog yields `(set) -> printedTotal` independently of the model, and that could check it. Unmeasured: how many wrong reads such a check would catch that the two name checks miss.

**Limit.** It converts misses into review taps and buys safety, not a higher T1 score.
