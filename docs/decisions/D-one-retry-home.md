## D-one-retry-home — Every network call retries through one method

Kind: build
Plan: docs/specs/stock-images.md#one-retry-home (python)

**The owner ruled it.** Every network call goes through one retry method. No caller writes its own `urlopen` loop, its own pauses or its own give-up.

**Why.** A call that gives up after one failure, or one that blinds its caller after one failure, costs the person a blank screen. The Sales stock-photo blank came from one DNS failure at start. Each caller with its own `urlopen` can repeat that mistake in its own way.

**The home is `pipeline/pricehistory.fetch_json`.** A caller passes its URL and reads an answer or one typed error (`Offline`, `Unreachable`, `Blocked`).

**Which failures retry.** No connection (`Offline`), HTTP 429, 502, 503 and 504. Each retries with a short backoff (`RETRY_PAUSES`) inside one time budget for all tries. A `Retry-After` header in seconds sets the pause. A pause that does not fit the budget is not taken, and the call gives up. A plain 500, a 403 and any other 4xx are never retried.

**When a host pauses.** A host pauses for `OFFLINE_WAIT_SECONDS` only after `PAUSE_AFTER_FAILURES` (3) failures in a row, each on a different URL. A failure here is a call that lost its retries on one of the retryable kinds above. Any success on that host resets the count. A plain 500 or a 4xx neither counts nor resets. The count is per host and shared by every caller in the process. A paused host is refused with no request.

**Two limits keep a run honest.** A URL that just lost its retries is not asked again for `OFFLINE_WAIT_SECONDS`. Many callers share one URL, such as the categories list. Without this limit, each caller would re-pay the retries and the run would never grow. And one product adds at most one URL to a run: a reading over several ranges stops at the first range that loses its retries. Without that limit, one product could pause the host alone.

**This narrows the `Offline` ruling.** A single HTTP error, or a single lost connection, never pauses anything. Only a run does.

**Measured.** On a stubbed network, 40 products through one `Market` on one host. When one product answers 500, the 39 others are served, with 40 requests and no retry sleep. When all 40 answer 503, the host pauses after the third product, with 9 requests and 6 s of retry sleep.

**Scope now.** The price fetcher (`pipeline/pricehistory.py`) is the first caller. `pipeline/stockimages.py` reaches the home through `Market`. These four files keep their own `urlopen` until a later lane moves them: `identify/match.py`, `server/order_transport.py`, `server/tcg_export.py`, `server/portal_http.py`.

**NOT MECHANIZED.** A machine would have to see each `urllib.request.urlopen` call outside the home, and fail on each one not in a shrinking offender list. The `capability homes` row of `make docs-audit` can be that machine once the home is named in it.
