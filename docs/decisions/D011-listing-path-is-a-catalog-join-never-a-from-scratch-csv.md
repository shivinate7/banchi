## D11 — Listing path is a catalog join, never a from-scratch CSV

**A listing is a catalog join against the export, never a CSV written from scratch.**

TCGplayer flow: Pricing tab → Export Filtered CSV (All Printings, so one file covers every variant) → pipeline fills fields → Import to Staged → review → Move to Live. Rows match by the `TCGplayer Id` SKU, which is never modified.
