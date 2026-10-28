# D8 — The Filtered CSV export is the price source

**Pricing comes from the TCGplayer Filtered CSV export and from no external API.**

It carries live, per-SKU, per-variant `TCG Market Price`. Threshold checks and pricing rules run directly against it.

pokemontcg.io data serves identification support (set IDs, collector numbers, printedTotal) and eval images only, never pricing. D15 vendors the same data locally and does not change that role. Nothing price-shaped is in that data, which is why a snapshot is safe. This entry names what the data is for. It does not authorize a call to the live API.
