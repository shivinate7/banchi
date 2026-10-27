# D216 — History host answers by User-Agent

The price-history host declines this project's default User-Agent, so Banchi sends a browser User-Agent through one setting.

Kind: process
Home: server/tcg_export.py

**`infinite-api.tcgplayer.com` answers this project's default `USER_AGENT` with a 403 and answers a browser User-Agent with 200.** The default is `pipeline.pricehistory`'s `USER_AGENT`, which names Banchi at version 1.0 and calls it a private single-operator inventory tool. No cookie, `Origin` or `Referer` changes either answer, so the User-Agent alone decides. `tcgcsv.com` answers either. Only the price-history reader (`pipeline/pricehistory.py`) is affected, and only for a SKU not already warm in the cache. So the panel looked alive wherever it had already been opened. A bare `curl` does not answer either.

- **One knob.** `server/tcg_export.py`'s `AGENT_ENV` (`BANCHI_TCG_USER_AGENT`) is D65's escape hatch for exactly this failure. It already means "the User-Agent to present to TCGplayer". No host in the walk needs a value the shared key cannot carry. `pipeline/` imports nothing outside itself, so the value is passed in: `fetch_json` and `Market` take an explicit `user_agent` defaulting to the project's `USER_AGENT`. `server/pipeline_routes.py` resolves it through `envfile.get_live`, since an operator edits it into a running process. It hands the value in at both call sites that construct a `Market`.
- **A 403 is `Blocked`, a sibling of `Unreachable` and never a subclass.** `history_unreachable` still means that a timeout, a 5xx or a non-JSON answer ("a mirror did not answer, and nothing is wrong with the run"). A 403 says the client is what is declined. It has its own code, `history_blocked`, which names `BANCHI_TCG_USER_AGENT` as the remedy. `_history_for_entry` catches both explicitly, so a missed case is a loud unhandled exception and not a 403 read as "try again".
- **The default is the project's `USER_AGENT`** for every checkout that sets nothing. A value for `BANCHI_TCG_USER_AGENT` lives only in the gitignored `.env`, like `TCGPLAYER_STORE_COOKIE`. `.env.example` carries the key and a comment and no User-Agent string. No refusal, return value or log line prints the value, only the key's name.

Reopen if a host blocks on something a User-Agent cannot answer (a TLS fingerprint, a required cookie, an `Origin` check). The answer is then D65's: retry by hand or accept the read is gone, as a new decision.
