## D-tcgcsv-daily-read — A daily read of TCGCSV builds a whole-market Riftbound price history

Kind: build

**The orchestrator picked it, on the owner's ask for "way more data" to backtest price patterns.**
The pick is reversible. The owner ruled the TCGCSV source and has not ruled this job step.

**Why it exists.** Every price history Banchi held covered only SKUs the store held or sold. TCGCSV
keeps a nightly copy of TCGplayer's prices for every product. Its past-days archive is withdrawn, so
a day not read is gone for good. `pipeline/dailyprices.py` reads Riftbound (category 89) once per
source update into the `daily_prices` table. The research in `docs/research/price-ta/` is the
reader. No screen reads the rows yet. A failed pass shows on the price-refresh note.

**The rules it keeps.**

- The day is the source's own update stamp (`last-updated.txt`), never the local clock. Two reads
  of one update store one day.
- A failed group leaves the update open. The next start fetches only the missing groups.
- Requests follow the site's own rules: a named User-Agent, a pause between requests, a throttle
  answer honored, and no file fetched twice for one update.
- Rows are never deleted (D219, the archive never deletes). One write per group (D88, one
  transaction per write).
- It rides the existing daily price job. It adds no launchd agent. It runs even when the refresh
  fails, because the refresh does not feed it.
- It never spends money.

**What would change it.** A reader on a screen. TCGCSV restoring its archive, which would make the
past fetchable again. Store size, if the table grows past what `make backup` copies comfortably.
