## DEBT70 — realized prices inform no listing rule

**Gap.** `#/product` shows what this seller got for a product against the archived market on each sale date (`GET /pipeline/products/<sku>/realized`, `pipeline/realized.py`). It is a read-only diagnostic. Nothing prices, lists or re-prices from it.

**How it is fed.** The server reads an OrderWand sales export in place, from the path in `PKMNSCAN_SALES_EXPORT`. With none set, the screen says so and reads nothing. The file holds buyer names. `read_sales` drops every column but nine at parse time. No copy of the file, and no buyer value, belongs in the tree, a fixture or a log.

**Limits.** The join is on `Vendor Product Id`. The export carries no SKU, so a product with several archived SKUs is compared against the SKU on screen, and the screen says so. A date older than the archive has no market figure and is left out of both averages. Refunded sales, purchases and non-USD rows are left out and counted. A listing rule built on this needs its own decision entry (D214: revenue is gross, never profit).
