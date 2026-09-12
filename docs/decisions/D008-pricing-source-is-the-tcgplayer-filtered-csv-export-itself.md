## D8 — Pricing source is the TCGplayer Filtered CSV export itself

**Pricing comes from the TCGplayer Filtered CSV export and from no external API.**

It carries live, per-SKU, per-variant `TCG Market Price`. Threshold checks and pricing rules run directly against it. No external pricing API.

pokemontcg.io data serves identification support (set IDs, collector numbers, printedTotal) and eval images only — never pricing. That role is unchanged by D15, which vendors the same data locally: the split above is why a snapshot is safe, since nothing price-shaped is in it. Read this entry as naming what the data is *for*, not as authorizing a call to the live API.
