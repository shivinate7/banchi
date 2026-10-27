# D319 — Every network call retries through one method

Kind: build
Plan: docs/specs/stock-images.md#one-retry-home (python)

**The owner ruled it.** Every network call goes through one retry method. No caller writes its own `urlopen` loop, its own pauses or its own give-up.

**Why.** A call that gives up after one failure, or one that blinds its caller after one failure, costs the person a blank screen. The Sales stock-photo blank came from one DNS failure at start. Each caller with its own `urlopen` can repeat that mistake in its own way.

**The home is `pipeline/net.py`.** `net.open` returns the status, the headers and the body of any HTTP answer. `net.request` returns the body, or raises `net.NetError` carrying the status. `net.open` is the one retry loop. A caller reads an answer or one typed error: `Offline` (no connection) or `Dropped` (the connection opened, then failed). `follow_redirects=False` hands a 3xx back with its `Location` and never sends a Cookie to a redirect. `pricehistory.fetch_json` is a thin JSON wrapper over it, with its own three errors (`Offline`, `Unreachable`, `Blocked`) and its own messages.

**A call is never refused unsent (owner ruling, no exemptions).** No flag opts out, and nothing refuses a call before its first request. Every call makes at least one attempt.

**Which failures retry.** No connection (`Offline`), HTTP 429, 502, 503 and 504. Each retries with a short backoff (`RETRY_PAUSES`) inside one time budget for all tries. A `Retry-After` header in seconds sets the pause. A pause that does not fit the budget is not taken, and the call gives up. A plain 500, a 403 and any other 4xx are never retried.

**A degraded host gets one attempt (owner ruling).** After `PAUSE_AFTER_FAILURES` (3) lost calls in a row to one host, each later call to it makes exactly one attempt, with no retry and no retry pause. Distinct URLs are not required: a lost call counts toward the 3. A lost call is one that lost its retries on a retryable kind above. Any HTTP answer but a 429 or a 5xx resets the count: a success, a 3xx, and a 400, 401, 403 or 404, because a host that answers is up. A plain 500 neither counts nor resets. The count is per host and shared by every caller in the process.

**The courtesy delay stays on a host that answers.** `Market` waits its courtesy delay between calls. It skips the delay only on a degraded host whose lost calls got no HTTP answer at all: a refused connection, an unreachable host or a timeout (`net.unanswered`). So an offline sweep stays fast. A degraded host that answers 429, 502, 503 or 504 is up and busy, and keeps the delay. A 429's `Retry-After` sets the least gap before the next call (`net.retry_after`). `net.retry_after` honors a `Retry-After` up to `REQUEST_TIMEOUT_SECONDS` and no further, and the call is still sent.

**Callers keep their own latches.** One product adds at most one URL to a run: a reading over several ranges stops at the first range that loses its retries. `Market` serves a stale catalog list after a failed refresh and asks again after `OFFLINE_WAIT_SECONDS`. `stockimages.FETCH_RETRY_SECONDS` leaves a failed pair alone, and is not shorter than `OFFLINE_WAIT_SECONDS`. These latches stop a caller, never a call: the call itself is always sent.

**This narrows the `Offline` ruling.** A single HTTP error, or a single lost connection, never degrades anything. Only a run does.

**A write retries only if it was never sent (owner ruling).** A call that changes something at TCGplayer passes `idempotent=False`. It retries only a connect-time failure: a refused connection, a failed name lookup, or an unreachable network or host. A status, a timeout, and a failure after any byte was sent (a broken pipe or a reset during the body) are raised at once with no second request, because a second request could list the same cards twice. A write neither counts toward a degraded host nor is limited by it, so a degraded host never weakens a rollback or a recovery write. The portal's export and the order search are POSTs that only read, so they retry like a GET.

**A login never follows a redirect (owner ruling).** With `follow_redirects=True`, a call that carries a Cookie or an Authorization header refuses a redirect to another host and never sends the header on. A call with no login header follows the redirect.

**The paid batch start is never retried (owner ruling).** `identify/batch.py` creates a batch with the SDK's `max_retries=0`, because a second create could start a second paid batch for the same cards. Retrieve and results are reads and keep the SDK default.

**Measured.** On a stubbed network, 40 products through one `Market` on one host. When one product answers 500, the 39 others are served, with 40 requests and no retry sleep. When all 40 answer 503, the host is degraded after the third product, with 46 requests (9 for the first three, then one each) and 6 s of retry sleep.

**Scope now.** These callers reach the home: the price fetcher (`pipeline/pricehistory.py`, and `pipeline/stockimages.py` through `Market`), `identify/match.py` (`download_model`, `fetch_bytes`, which keeps its gap between request starts), and the two TCGplayer hosts through `server/portal_http.py` (`server/order_transport.py`, `server/tcg_export.py`, and `server/tcg_import.py` as `idempotent=False`). `identify/batch.py` is the SDK's own transport and follows the paid-start ruling above. A Card Ladder caller, when one is built, reaches the home the same way, as `idempotent=False` for a write.

**NOT MECHANIZED.** A machine would have to see each `urllib.request.urlopen` call outside the home, and fail on each one not in a shrinking offender list. The `capability homes` row of `make docs-audit` can be that machine once the home is named in it.
