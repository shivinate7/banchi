## D106 — The push and the publish are two presses, and the second one is the only thing here a buyer can see

**The markdown sheet sends `import.csv` to TCGplayer itself, and moving those prices live is a separate press.** Built 2026-09-06 on the owner's instruction, after being shown that the flow ended in a downloaded file and a manual trip through the seller portal: *"like mimicing the tcgplayer button yourself? sure."*

`server/tcg_import.py` is the transport, `POST /pipeline/markdowns/<stamp>/push` and `POST .../publish` are the routes, and steps 3 and 4 of the sheet are the two presses.

### Why it is not one button

**Because the margin that saved this project on the day it was built was exactly the gap between them.** A session driving TCGplayer's importer as a dry run armed an interceptor from the bundle's *function* names — `uploadPrices`, `finalizeUpload` — while the wire names are `uploadexportcsv`, `finalizeexportcsv`. Nothing matched, nothing was blocked, and 100 real rows went up. It cost nothing, and the whole reason it cost nothing is that `Import to Staged` is not `Move To Live`: measured immediately afterwards, **0 of 759 live prices and 0 live quantities had moved**.

A single button would spend that margin for one saved click. So the sheet has four steps, the fourth is drawn apart from the other three with its own rule and its own red press, and the route behind it is the only one in this server that can change what a buyer pays.

### What the transport promises, and why it is not in `tcg_export.py`

That module's docstring makes four promises and the second is **"It cannot cause a charge."** A write beside it would either falsify that or narrow it to a technicality, which is the move D16 exists to catch. So the write is its own file, under its own promises:

- **Two operations, both explicit.** Nothing implicit, cached, or retried on the caller's behalf.
- **A move is scoped to ONE upload and cannot be scoped any other way.** TCGplayer's own control offers three scopes — 1 "This Page", 2 "My Search Results", 3 "this upload" — and `SCOPE_THIS_UPLOAD` is a **constant, not a parameter**, because 1 and 2 would publish rows this pipeline never staged and cannot describe.
- **The upload id comes off disk, never off the request.** `publish` reads the push receipt, so a replayed or mistyped body cannot publish an upload this markdown never made. The id *is* the scope, which is what makes that guard load-bearing rather than tidy.
- **A failed push is rolled back**, not left as a pile of staged rows the operator has to find by hand.
- **`AddToQuantity` must be 0 on every row or the file is refused** — D100's invariant, asserted a fifth time and at the last possible moment. That is what makes an accidental re-upload a no-op.

**The transport is borrowed, not copied.** `tcg_export._open` carries the redirect discipline — one hop, never to the logon page — and D104 settled that this rule gets one implementation because it is the part that rots in a copy.

### The contract was read, then adversarially verified, and one detail was only found that way

`docs/specs/tcgplayer-portal-api.md` is the map. Every field came out of TCGplayer's own 652KB bundle, which is **served without authentication**, so it can be re-read at any time. A 157-agent adversarial pass over it confirmed the four endpoints, `CHUNK_SIZE = 750`, the parallel chunk fan-out, and the absence of any anti-forgery token.

It also caught what symmetry would have got wrong: **`initializeexportcsv` takes lowercase `filename` and `uploadexportcsv` takes camelCase `fileName`.** Their bundle really does spell it both ways.

**`connectionId` looked like a blocker and is not.** It is a SignalR handle for progress callbacks, and their own `establishConnection` resolves inside `.always()` — their client proceeds when the hub connection fails. A Python client loses the percentage, not the operation, and sends it empty.

### What is measured and what is not

**The push is measured**, end to end, on the owner's account: three POSTs, a 100-row file, `Validated 100 records`, `100 products were successfully imported`, and 0 live rows changed.

**And so is the publish, as of 19:25 UTC the same day.** On the owner's explicit instruction, Vilemaw (Riftbound, Epic, Near Mint Foil, 4 live) went **$23.22 → $750.00 → $23.22** through this repo's own routes: `push` accepted 1 of 1, `publish` answered `Update: [Vilemaw / Marketplace]` with zero errors, the portal's Live grid showed $750.00, and the revert put it back. The spec's §6 carries the timeline.

**What that measurement also caught: `Export From Live` is not read-your-writes.** Roughly forty seconds after a confirmed publish the export still served the OLD price while the grid served the new one. `pkmnscan reconcile --live` reads that export and writes `live` off it (D87), so a reconcile run straight after a publish records the pre-publish price. Nothing guards it, and the export was believed here until the grid contradicted it. That is a defect in the reconcile's timing, not in this path, and it is recorded rather than fixed.

### The lag has a guard, and it is a filter rather than a refusal

`cli/cmd_reprice.py:published_recently` reads the markdown receipts — `push.json` says WHEN, the `import.csv` beside it says WHICH — and `reconcile --live` will not settle a SKU published inside `PUBLISH_LAG_S`. It keeps the store's own figure and **names the SKU in the report**, which is D87's own posture for a reading it will not take, pointed at a second clock.

**It narrows to SKUs rather than blocking the reconcile**, because the rest of the store is not in doubt. And it is computed BEFORE the preview, not just before the write: `_settlement`'s docstring promises the preview "cannot promise a correction the write then refuses", and a skip applied only on the write path would break exactly that, silently, in the output the operator reads first.

**`PUBLISH_LAG_S` is 15 minutes, and that is a choice rather than a reading.** The staleness was measured at ~40s; **when the export actually converges was never measured**, because measuring it costs another live price change. The window is deliberately generous: too long costs a reconcile repeated later, too short writes a wrong number into `live` — the field `cli/resolve.py:_copies_out` treats as a floor that cannot be argued below. The constant carries the experiment that would replace it with a measurement.

**A receipt this cannot date is treated as RECENT, not as old.** The guard exists to refuse a figure it cannot vouch for, and an unparseable stamp is exactly that.

### The rollback is on the screen, and it is narrower than the portal's own

`POST /pipeline/markdowns/<stamp>/rollback` and a **Discard staged** button beside the publish. `rollbackexportcsv` was implemented in the transport and reachable from no button, which by CLAUDE.md's hard rule meant it was not built.

**It is offered only before the upload is published**, because afterwards TCGplayer no longer holds those rows staged and a live price goes back the way it came down — another markdown (D100). And it is `rollbackexportcsv` and never `clearstagedinventory`: the latter takes no id and empties the operator's whole staged channel. A scope that can widen is not something a button should be able to choose, which is `move_to_live`'s rule applied to the undo.

### What would reopen this

*A measurement of the export's real convergence time*, which retires the guessed window. *An operator who wants to publish a subset of one upload*, which TCGplayer's scopes cannot express and would need a second staged upload instead. *Raises* — `docs/specs/stale-listings.md` §6b — which this path refuses today and the owner has asked for.
