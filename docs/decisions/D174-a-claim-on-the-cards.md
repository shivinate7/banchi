## D174 — A press claims the cards it is about to buy, and the claim is written in the transaction that decides what they are

**The only binding in this pipeline that protects a dollar was a BOX NUMBER, and a box number is wrong in both directions. It is now a set of position keys, written by the command that spends, inside the same `Store.write()` that recomputes what is being bought — because the send list is decided a minute before the claim, and two presses can both finish deciding before either has claimed.**

### What stood before this, and exactly what it covered

`server/pipeline_routes.py:_busy_run(box)` refuses a second `POST /pipeline/identify` while a live run is reading the same box. That is the whole of the money guard, and its own docstring is honest about the shape: *"the guard is against a double-click, not against an attacker: two live batches over one box is the shape that turns one invoice into two."*

**The identification cache cannot stand in for it, and that is the load-bearing fact.** A cache entry is written AFTER collection — `cli/cmd_identify.py` puts it in the transaction that records the answers — so two presses racing each other both consult an empty cache, both compute the same misses, and both pay. The cache makes the SECOND press free only once the first has finished.

### The box number is wrong in both directions

**TOO WIDE.** Two live runs over disjoint selections in one drawer are refused. `_busy_run` says so in as many words — *"It narrows what is allowed, deliberately"* — and D48 records that narrowing as accepted for want of a card-level vocabulary. Nothing was ever going to be double-billed there: the two presses are buying different cards.

**Too narrow, and this is the half that costs money.** `_run_box` answers `None` for a run whose captures span more than one box: `cli/cmd_identify.py:_scope_for` returns no scope block when the sidecars name two boxes (*"A run whose captures name two boxes gets NO scope rather than a guessed one"*), and the capture directory's name does not parse as `boxN` either. So a run over a multi-box pile is **invisible to the guard in both directions** — a box press and that run do not see each other, and the overlap is billed twice.

**Widening `_busy_run` to be store-wide does not fix this.** A store-wide press and a box press would still resolve to `None` and `3`, which are not equal, so they would still not see each other. The vocabulary is the problem, not the scope.

### The rule

**A press claims the POSITION KEYS it is about to pay to read, in the `submissions` table, and a second press is refused on INTERSECTION.** A key is `box/index` (`identify/sidecar.py:key`) — the same string the cache, the queues and the join are keyed by — so a claim over two drawers is one row and a claim over three cards is three strings. Neither fault above survives it: disjoint selections in one drawer do not intersect, and a press spanning drawers intersects a box press on the cards they actually share.

**The refusal names the receipt and the overlapping cards.** `store/submissions.py:conflict_sentence` composes it once for both refusal sites, because a money refusal spelled two ways is two messages an operator has to learn to read as one thing. The cards are truncated and the COUNT is not: a press overlapping two cards is a double-click and one overlapping four hundred is a different mistake, and the number is what says which.

### What is claimed is the send list, never the selection

**This is the property that keeps the guard worth arming at all.** On the operator's store 2,321 of 2,535 cards are cache hits, so a press over everything claims **~214 keys** and leaves the other 2,321 free for any other press. A table that claimed the selection would lock the store on the first press, which is a guard nobody would keep armed — and switching a money guard off is worse than not having written it.

**A press whose send list is empty writes no row at all.** It is spending nothing, so there is nothing to protect. That is the limit case of the same rule rather than an exception to it.

### The check and the write are one transaction, and the send list is recomputed inside it

The send list is decided by `cmd_identify`'s hash-and-consult pass, which on 678 photographs is **a minute of decoding** before the claim — the hash-first reorder's own measurement. So two presses can both finish deciding and both arrive believing they are first. **`claim_or_refuse` therefore recomputes the miss set from the cache it is handed, intersects against the live claims read in that same transaction, and writes the row before the lock is released.** D88 is what makes that one act: `BEGIN IMMEDIATE` under the flock, one commit over every table.

**The caller passes the digests it already computed.** Hashing thousands of photographs under the store lock is not something to do; the digests are properties of the bytes on disk and cannot move under a press, while the cache and the other claims can, so only those two are read inside.

**Where the recompute NARROWS the send list, the dropped cards adopt the answer the store now owns.** `cli/cmd_identify.py:_adopt_cached` exists for that second caller. A card dropped from the claim and still submitted would be paid for with nothing holding it; reported as a failure instead, it would be an `identification_failed` queue entry for a card whose answer is sitting in the store.

**`force` is the deliberate re-read, and without it this would have silently broken one.** Every `--reidentify-stale` target is a cache HIT by construction — that is what it is for — so recomputing from the cache alone would drop all of them from the claim and the run would submit cards nothing was holding.

**`resuming` is a run continuing, not a second press.** `--run-dir` re-enters a run that already claimed these cards and died, and its own stale claim is the first thing the resume collides with. Naming the run releases THAT run's claims and no others, which is what keeps it from being a back door: a caller can only ever name the run it is re-entering.

### A row does not self-heal, and it is not allowed to

`_busy_run` recovered from a wedge by itself, because `_CHILDREN` empties on a restart and the marker file's pid stops resolving. **A row in the store survives every restart there is, and that is the point rather than a defect.**

**A run killed after it submitted has a batch in flight at Anthropic that nobody collected, and the results keep for 29 days.** A guard that dropped the row on finding the pid gone would hand the operator a green button over an invoice already rung up. So a live row blocks whatever its holder is doing, and `holder_alive` is **reported** rather than acted on — the screen says WAIT for a live holder and offers the release for a dead one, and the choice stays the operator's.

**Liveness is read, never guessed from an mtime**, which is `scripts/janitor.py`'s rule for its own subject. The pid, plus the `ps -o lstart=` string recorded at claim time and compared on read. **The comparison is exact where janitor's needs a 120-second tolerance**: that function compares a session record's `startedAt` (epoch milliseconds, UTC) against `ps` (local time) and its docstring records what the mismatch cost — every session judged dead, and a sweep offering to reap the tree it was running in. Both values here come from one source in one format.

**The console app's own per-session records are deliberately NOT consulted, and the deviation is argued rather than silent.** That directory — one JSON per pid, under the user's own `~/.claude` — answers "which tree is a Claude session standing in", and the holder of a submission is a `pkmnscan identify` child — not a Claude session. A session record says nothing about it, and reading one would add an oracle that can only produce a wrong answer. What transfers from janitor is the METHOD: a recorded fact about the process, compared on read, failing toward live.

**Failing toward live is the safety direction.** A false "live" over-refuses a press and the operator releases the claim; a false "dead" is the double invoice. Everything unreadable — a `ps` that will not parse, a missing `proc_start` — reads live.

### One release is not the banking commit, and it is keyed on proof

**A submission that failed before sending anything releases its claim** — `cli/cmd_identify.py:_give_back_unspent`. It is the only place a claim is given back without its answers being banked, and it is safe for exactly one reason: `run_dir.batch_ids` is empty. `identify/batch.py` records every id through `on_submit` **as it submits**, so no id is proof no chunk reached the API and there is nothing in flight to collect.

**It is not a `finally`, and the distinction is the whole point.** A submission that dies part way has ids recorded and batches paid for, keeping for 29 days — so a caught exception cannot tell an unspent press from a half-spent one, and releasing on the exception would be the double invoice arriving through the door built to relieve it. The ids can tell. A half-sent press keeps its claim and the report says so, naming `--run-dir` as the way to resume the run that holds them.

**What it is for is the ordinary self-inflicted failure**: a missing or bad API key on the first press of a fresh checkout. Measured — a real press with a bad key claimed 3 cards, took a 401, and released them, naming why it was safe. Without this, that typo in `.env` leaves a drawer's worth of cards claimed by a run that spent nothing, and every later press refused until somebody goes and releases it by hand.

### The way out is a press with a receipt on it

**A route is not a feature, so the release is the whole chain.** `POST /pipeline/submissions/<receipt>/release`, `releaseSubmission` in `app/src/server.ts`, and a panel on `#/runs` — `app/src/SubmissionClaims.tsx` — where the refusal already sends the operator: *"watch that run, or release its claim."*

**The free count comes before the control that fires**, which is D89's shape for the photo reclaim and D34's before it. `GET /pipeline/submissions` reads the store and holds nothing, and the release button does not exist until it has answered — so the receipt, the run, the card count and whether the holder is still alive are all on screen before anything can be pressed.

**A live holder is not offered a release at all.** Releasing a claim whose run is still submitting re-opens those cards to a second press, and that press is the double invoice the claim exists to prevent. The button is drawn only for a claim whose holder is gone; a live one says what to do instead. That is not a disabled control — D50's `not-allowed` is for a control that exists and cannot be used right now, and this one does not apply.

**The panel draws nothing when nothing is claimed**, which on a healthy store is almost always, and that is why this is a panel rather than a thirteenth route: a route for it would be a nav item leading to an empty page.

### Two refusals, and only one of them is the guard

**`store/submissions.py:claim_or_refuse` is binding.** It is called by the command that spends, inside the transaction that decides what is being bought, so it is the only refusal that is atomic with respect to another press — and it covers every press path, the screen's, a terminal's and an agent's, because it is in the one command all three go through.

**`server/pipeline_routes.py:_claim_conflicts` is a courtesy, and it is written down as one.** It reads the live claims and intersects them against each leg's SELECTION keys — which needs sidecars and no digests, so it is cheap enough to run at a press — and refuses the whole cart before a single child is started. It can be beaten by a press landing between the read and the spawn. Its job is to answer the ordinary double-click AT THE PRESS with a sentence, instead of by a child that starts, refuses and dies as a red row on the screen.

**What the courtesy check can over-refuse, named rather than hidden**: a card of mine that is a cache hit and somebody else's live miss. My press would pay nothing for it and is refused anyway, for as long as their claim stands. That is the correct trade at a money press.

**`_busy_run` is left in place by this entry.** Both checks now run in `do_pipeline_identify`. Deleting its callers is a separate change with its own reasoning, because a guard is removed only once its replacement has been exercised.

### The work is counted, not the outcome

The addendum to the hash-first change records deleting its own gate and watching every outcome assertion stay green, because hash-first and decode-everything agree on every ANSWER. **A guard has that failure available to it in a sharper form: a claim table that claimed nothing would let every press through, and every "the press succeeded" assertion would still pass.**

So the figures are published rather than inferred from the fact that nothing has gone wrong. `submissions.counted` answers rows live, **cards locked**, and dead holders; `GET /pipeline/submissions` puts all three on the wire; the panel draws the card count beside the row count, because one claim over four hundred cards and four claims over one card each are the same row count and completely different situations; the command's own report says how many cards it held and that it gave them back.

**And the suite refuses to pass over nothing.** A run whose total is zero exits non-zero, a case that recorded no checks is a failure in its own right, and the attempted count is compared against `CASES` rather than trusted. That floor is here because the shape is measured elsewhere in this repo: `scripts/docs-audit.py`'s reporter prints `ok` for an empty findings list, so `paths 0 references resolve` reads green over no subject at all. It is the same hole this table guards in another register — a guard holding nothing passes every assertion about what it holds.

`make submission-selftest` asserts those counts, and `case_claims_the_send_list_only` exists for no other reason — it is the only case that can tell the send list from the selection, because every other case in the file passes either way.

### How it is proved

**`make submission-selftest`** — in `make check`, never in the git hook (D18: it writes a temp store and it signals processes), the same standing as `janitor-selftest` and `reap-selftest`. Every case runs against a throwaway store with `PKMNSCAN_HOME` repointed, because the press this guard stops costs money and "run two presses at the operator's store and read the invoice" is the incident rather than the test.

**It reproduces the bug before it proves the fix**, which is `reap-selftest`'s rule — that file reproduces `pkill -f` with real processes rather than asserting it would have been wrong. One case runs two real processes in the check-then-claim order anybody writes first and watches **both** buy the same card; the next runs them through `claim_or_refuse` and exactly one wins, six rounds out of six. Without the first, the second proves only that something happened.

**The barrier is a barrier, not a sleep** (D136). The naive children synchronise twice — once to start, once after each has read and before either writes — so the window is held open by construction. A probabilistic reproduction of a money bug is a flake.

**Mutation-tested: sixteen arms, all killed** — ten over the claim, two over the schema upgrade (the one path a store that already holds 2,535 cards actually takes), two over the release door below, and two over the suite's own floor against examining nothing. Two arms paid for themselves. One survived the first pass: every store-wide case shared its card with the LOWEST-numbered box in the pressing selection, so a guard narrowed to the first drawer it saw passed all four directions. The case with the overlap two drawers along was added for it. The other found **two assertions of the suite's own passing for the wrong reason** — a `Store` built before the case's second `fresh_store()` was still bound to the first store's directory, so a release that should have fired missed, and both the "it did not release" and "the cards stay held" checks read right for the wrong cause. The symptom was an arm killing one assertion of four instead of three.

### What is NOT proved

**The REFUSAL has been through the real command, including the case the box form cannot see.** Both were driven by hand on 2026-09-12, and in both the preflight printed, the refusal named the run, the receipt, the card and the remedy, the command exited **1**, **no run directory was created at all** — which is what writing the claim before `runs.create` buys — and the standing claim was left untouched. `--dry-run` over the same directory claimed nothing, as it must.

- **A box press over cards one of which was already claimed.** The ordinary double-click.
- **A press over a PILE whose captures span boxes 3 and 8, against a live claim on 8/7.** `_run_box` answers `None` for that run — confirmed directly, not assumed — so `_busy_run(8)` can never match it and the old guard was blind in both directions. The claim table refused it on the card in the pile's *second* drawer.

**What has NOT happened is a claim written by a press that went on to spend.** The self-test races `claim_or_refuse`, which is the mechanism and the same call the command makes; it is not `pkmnscan identify` through to collection, which needs the Batch API, and a test that mocked the API would be racing the mock. So **the release path — the claim given back by the commit that banks the answers — has never run**, and no invoice has been prevented in production. The first real press is what measures both.

**The release control has not been exercised against a real stuck claim.** Its chain is complete, typechecked, and pressed for real against a seeded claim whose holder had been killed with `-9` — the row went, the figures fell, and the receipt named the run. What it has not met is a run that died mid-batch on the rig, which is the case it exists for.
