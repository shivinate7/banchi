## DEBT69 — the daily price read covers listed SKUs only, and no live price is pushed automatically

**Gap.** `scripts/price-refresh-daily.py` downloads the owner's own live listings once a day, and `#/pricing` shows which listed items moved more than 10% since listing. Two things are not covered. A card held but not listed is in no live export, so nothing refreshes its market on a schedule. And "since listing" needs an archive bucket for the listing day, which only an archive sweep writes (DEBT32, still a press), so a listing the archive never read is counted as unchecked on the panel.

**Not this debt.** An automatic push of new live prices needs its own decision entry. It takes the shape of a free preflight that shows each change, then a confirm that is not a default. An unattended loop that moves live prices is the one thing here that can lose money unseen.

**Outcome at risk.** A held, unlisted card is priced from a market reading as old as its last run or fetch.

**Closes when.** A scheduled scoped catalog fetch is argued for held SKUs (it needs a set scope per game, and a Pokemon run that widens is refused), or the owner rules that listed SKUs are enough.
