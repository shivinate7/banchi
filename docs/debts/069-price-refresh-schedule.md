## DEBT69 — the daily price read skips some runs, "moved since listing" needs an archive bucket, and no live price is pushed automatically

**Gap.** `scripts/price-refresh-daily.py` runs `pipeline_routes.do_prices_refresh` once a day (D104). It downloads the owner's own live listings, fetches the catalog export once per game, re-joins every open run and reads the sales history. That prices every copy held but not listed. `#/pricing` shows which listed items moved more than 10% since listing. One thing is not covered: "since listing" needs an archive bucket for the listing day. Only an archive sweep writes that bucket (the daily job sweeps it after the refresh, D224). So a listing the archive never read is counted as unchecked on the panel.

**What the morning read still misses.** Each case leaves the last good prices in place, and the note names the failed step.

- A run whose last join failed waits for its own retry. The refresh does not try it again (one fetch a day, D104).
- A run that holds several games is dropped when one game's catalog fetch fails. It joins against all its games' files or not at all.
- If the open runs cannot be read, nothing is joined that day.
- An unhinted Pokemon run is refused (D170), so it is not priced.
- The note shows only the first problem of a step, not every run that failed.

**Not this debt.** An automatic push of new live prices needs its own decision entry. It takes the shape of a free preflight that shows each change, then a confirm that is not a default. An unattended loop that moves live prices is the one thing here that can lose money unseen.

**Outcome at risk.** A listing the archive never read shows as unchecked, so a price move since listing can go unseen. A run the morning read skips is priced from its last good join.

**Closes when.** The listing-day bucket is written even on a day the Mac is off (DEBT32), or the owner rules that an unchecked listing is enough.
