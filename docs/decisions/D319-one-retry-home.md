## D319 — Every network call retries through one method

Kind: build
Plan: docs/specs/stock-images.md#one-retry-home (python)

**The owner ruled it.** Every network call goes through one retry method. No caller writes its own `urlopen` loop, its own pauses or its own give-up.

**Why.** A call that gives up after one failure, or one that blinds its caller after one failure, costs the person a blank screen. The Sales stock-photo blank came from one DNS failure at start. Each caller with its own `urlopen` can repeat that mistake in its own way.

**The home is `pipeline/net.py`.** `net.open` returns the status, the headers and the body of any HTTP answer. `net.request` returns the body, or raises `net.NetError` carrying the status. `net.open` is the one retry loop. A caller reads an answer or one typed error: `Offline` (no connection), `Dropped` (the connection opened, then failed) or `Paused` (the host is paused). `follow_redirects=False` hands a 3xx back with its `Location` and never sends a Cookie to a redirect. `pricehistory.fetch_json` is a thin JSON wrapper over it, with its own three errors (`Offline`, `Unreachable`, `Blocked`) and its own messages.

**Which failures retry.** No connection (`Offline`), HTTP 429, 502, 503 and 504. Each retries with a short backoff (`RETRY_PAUSES`) inside one time budget for all tries. A `Retry-After` header in seconds sets the pause. A pause that does not fit the budget is not taken, and the call gives up. A plain 500, a 403 and any other 4xx are never retried.

**When a host pauses.** A host pauses for `OFFLINE_WAIT_SECONDS` only after `PAUSE_AFTER_FAILURES` (3) failures in a row, each on a different URL. A failure here is a call that lost its retries on one of the retryable kinds above. Any success on that host resets the count. A plain 500 or a 4xx neither counts nor resets. The count is per host and shared by every caller in the process. A paused host is refused with no request.

**Two limits keep a run honest.** A URL that just lost its retries is not asked again for `OFFLINE_WAIT_SECONDS`. Many callers share one URL, such as the categories list. Without this limit, each caller would re-pay the retries and the run would never grow. And one product adds at most one URL to a run: a reading over several ranges stops at the first range that loses its retries. Without that limit, one product could pause the host alone. A success on another URL does not lift a URL's wait. A plain 500 or a 4xx sets no wait and stops no range.

**This narrows the `Offline` ruling.** A single HTTP error, or a single lost connection, never pauses anything. Only a run does.

**A write retries only if it was never sent (owner ruling).** A call that changes something at TCGplayer passes `idempotent=False`. It retries only a connect failure before any byte is sent. A status, a timeout, a dropped connection and a reset are raised at once with no second request, because a second request could list the same cards twice. A write neither checks nor records the host pause, so a paused host never blocks a rollback or a recovery write. The portal's export and the order search are POSTs that only read, so they retry like a GET.

**The TCGplayer portal takes no part in the host pause.** `server/portal_http.send` passes `host_pause=False`. Every call there is an operator's press, and a press must never be refused for a wait an earlier press set. It still retries by the rule above.

**The paid batch start is never retried (owner ruling).** `identify/batch.py` creates a batch with the SDK's `max_retries=0`, because a second create could start a second paid batch for the same cards. Retrieve and results are reads and keep the SDK default.

**Measured.** On a stubbed network, 40 products through one `Market` on one host. When one product answers 500, the 39 others are served, with 40 requests and no retry sleep. When all 40 answer 503, the host pauses after the third product, with 9 requests and 6 s of retry sleep.

**Scope now.** These callers reach the home: the price fetcher (`pipeline/pricehistory.py`, and `pipeline/stockimages.py` through `Market`), `identify/match.py` (`download_model`, `fetch_bytes`, which keeps its gap between request starts), and the two TCGplayer hosts through `server/portal_http.py` (`server/order_transport.py`, `server/tcg_export.py`, and `server/tcg_import.py` as `idempotent=False`). `identify/batch.py` is the SDK's own transport and follows the paid-start ruling above. A Card Ladder caller, when one is built, reaches the home the same way, as `idempotent=False` for a write.

**NOT MECHANIZED.** A machine would have to see each `urllib.request.urlopen` call outside the home, and fail on each one not in a shrinking offender list. The `capability homes` row of `make docs-audit` can be that machine once the home is named in it.
