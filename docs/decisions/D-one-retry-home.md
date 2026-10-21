## D-one-retry-home — Every network call retries through one method

Kind: build
Plan: docs/specs/stock-images.md#one-retry-home (python)

**The owner ruled it.** Every network call goes through one retry method. No caller writes its own `urlopen` loop, its own pauses or its own give-up.

**Why.** A call that gives up after one failure, or one that blinds its caller after one failure, costs the person a blank screen. The Sales stock-photo blank came from one DNS failure at start. Each caller with its own `urlopen` can repeat that mistake in its own way.

**The one home owns three things.** It decides which failures are worth a second try. It decides the time budget for all tries together. It decides when a run of failures stops further asks for a while. A caller passes its URL and reads an answer or one typed error (`Offline`, `Unreachable`, `Blocked`).

**Scope now.** The price fetcher (`pipeline/pricehistory`) is the first caller. `pipeline/stockimages` reaches the home through `Market`. These four files keep their own `urlopen` until a later lane moves them: `identify/match`, `server/order_transport`, `server/tcg_export`, `server/portal_http`.

**Open: the pause rule.** The rule that stops further asks after a run of failures is not settled. The owner is choosing it.

**NOT MECHANIZED.** A machine would have to see each `urllib.request.urlopen` call outside the home, and fail on each one not in a shrinking offender list. The `capability homes` row of `make docs-audit` can be that machine once the home is named in it.
