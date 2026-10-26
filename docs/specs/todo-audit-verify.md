# Opus check of the to-do audit

> **Done**
> - OTHER: PASS, no round named, Opus. 32 of the 40 claims I checked hold (80%). 7 are PARTLY and 1 is mis-sorted. I read origin/main at a4f6de77. Report: `/private/tmp/claude-501/-Users-shivinate-Developer-banchi/67d55b5f-cfa5-49e0-bbc7-05fb884cd7f2/scratchpad/todo-audit.md`
>
> **Section 1, close the record: 21 checks, 17 CONFIRMED, 4 PARTLY, 0 WRONG**
> - CONFIRMED d076 (phone walk sheet has no Mark sold). `Orders.OrderPickPane` passes `detail` (`CardLocations` with `OrdersWalkPane.RowAction`) into the phone `Sheet`. Both named comments are stale. `CardHero.CardPane` says "NO `detail`". `RowAction` says "the pane omits it", but the pane now passes `take`. No running check proves the fix: the 390 cases are skipped while `PHONE_SPECS_ON` is false.
> - CONFIRMED d011 (request lanes). `capture_server.PHOTO_LANE_EXACT` now has `/pipeline/match`, and `PHOTO_LANE_PREFIXES` has `/pipeline/match/sweep?keys=`.
> - CONFIRMED d084 (demo first-load weight). `HOME_FIRST_LOAD_BUDGET_BYTES` is 8.5 MiB, against 8.32 MB measured. Caveat: the budget was set just above that measurement. The case runs after merge, on each push to main that touches `demo-assets/**` (`demo.yml`). I did not read its current result.
> - CONFIRMED, one line each:
>   - **my-slabs header and the three D320 (My Slabs reads Card Ladder) checks:** `cardladder.ALLOWED_CALLABLES`, the host refusal in `cardladder-selftest`, and "No sales" in `slabs.spec`.
>   - **stability header:** §7 says "Built".
>   - **box-map:** `.shelf-pair` is `flex-direction: column` at every width.
>   - **capture-app 19:** 6 `LADDER_REASONS` plus 13 `ROUTING_REASONS`, with no overlap.
>   - **motion-trigger:** `RIG_CEILING_PER_HOUR` has 0 hits in code.
>   - **card-detail:** kit `Meter` and `bn-dot-still` exist; `data-flip` and `browse-hero-chips` are gone.
>   - **one-process:** §4 has no idle hold, but `serve.IDLE_SECONDS` is 300. §5 and §10 say six keys; there are ten.
>   - **demo stock-images note:** the stock-images spec says BUILT.
>   - **lean-server §7 sizes:** home-assistant §1 measures the store at 126 MB and `inventory/` at 733 MB.
>   - **sales-findings rescale:** the bucket bars use `gross / bmax`, from zero.
> - PARTLY d064 (collector number not cross-checked). The gap is closed by the `name?:` rung in `join`. But the report describes the code wrongly. A name that resolves to one card is listed. `NUMBER_UNREAD_NAME_MATCHED` queues only when `distinct_cards(found.rows) > 1`.
> - PARTLY lean-server "Nothing is built". Options (a) to (e) are not built. Only the header sentence "no code, route or setting exists" is false.
> - PARTLY multi-game. Riftbound has met real photos: D35 (unread numbers use the name) records run `2026-08-29-box1-01` with 133 cards. "324 cards, box 3" is UNKNOWN, because the store is off limits. "Never read a card" in `games.py` is false. Its "UNMEASURED" note on prompt accuracy can stay.
> - PARTLY demo §8. The spec table has 7 rows and `demoServer.CANNOT` has 8. The fix adds a `/pipeline/match/prepare` row, not only a new count.
>
> **Section 2, data defects**
> - CONFIRMED d087 (Unhold receipt before the store write). Failure path: `send_routes._unhold` writes `unheld` to the receipt inside `Store().write()`, then calls `_bump_back`. If the commit fails, the receipt keeps `unheld` and the store keeps `held_copies`. The next `_hold_removed` then clears the count, so the Unhold control is gone. `_bump_back` never raises, so only a store fault splits the two.
> - PARTLY d095 (typed price on an at-cap row). `Pricing.typedPrices` never reads `at_cap`. But `Pricing.priceChanges` does send a typed price on an at-cap row that is live at a different price. The tile and the send disagree only when the row has no live copies or the price is unchanged.
> - WRONG as sorted: Rank 33 (a copy offered twice). Neither the backlog nor the code shows a failure path. `resolve._copies_out` and `join.uncommitted_positions` guard it today. D59 (live count is per SKU) calls the per-copy marker "available, not owed", and the two cases D59 gives up send too few copies, not too many. Building the marker reopens D59, so it belongs in section 3. I did not prove that no path exists.
> - CONFIRMED d040 (divider save past departed cards). In the middle branch, `join.divider_index` returns `occupied[ordinal-1]` and never reads `departed`. Departed records before that card fall into the previous section.
> - CONFIRMED d004 (tune-only T1 run). With `BANCHI_T1_SPLIT=tune`, the holdout group is empty, so `holdout_accuracy` is None. `t1_id_eval._write_results` then overwrites `harness/results/t1.json`. Nothing checks the split before the write.
>
> **Section 2 spot-checks: 14 checks, 12 CONFIRMED, 2 PARTLY**
> - CONFIRMED:
>   - **d098:** with nothing to send, `cmd_identify.run` sets `ready` False and the basis "certain", so `RunsComposer` draws "not set up".
>   - **d020:** the orphan branch of `pipeline_routes._live_pid` is signal 0 only.
>   - **d086:** 61 bare `toLocaleString()` calls. There are 13 `<details>`, not about 10.
>   - **graveyard:** the `BoxBrowse` shelf is `useState`, and deep links set number shelves only.
>   - **d003:** `cmd_identify` builds `master.Card(...)` by hand, and 41 of 62 spec files import no wire type.
>   - **identify-engine-pick:** §3 reports 3,001 photos with 0 wrong, so its "not yet measured" line is stale.
>   - **d025:** confirmed.
>   - **sales-findings percent:** `Revenue.compareClause` has a zero guard and no floor.
>   - **d099:** `luminance_p99` decodes each pending photo at full size before the quote.
>   - **d027:** `Fulfillment` calls `getInventory()`.
>   - **d060:** the `IS_DEMO` stopgap is still in `Orders`.
> - PARTLY d008 ("Unnamed Box" typed). `BoxOps` is fixed; only `Fulfillment` is left. d008 says "no work proposed", and the report lists it in both section 2 and section 4.
> - PARTLY Rank 31 (a terminal identify writes no `running.pid`). The claim is true (`cmd_identify._own_pid_marker`). But `submissions.claim_or_refuse` (D174, a paid press claims its cards atomically) already stops the double spend. Only the screen's busy view is left.
>
> **Section 5, unclear**
> - RESOLVED, real defect: the sales-findings prior window overlaps the current one. `Revenue.windowsOf` with `inPrevious` (`previousStart + elapsedMs`) overlaps by 1.9 days for the 3-month preset on May 31, and 2.9 days for the 6-month preset on Aug 31. Sales in the overlap count in both windows. Move this to section 2.
> - d050: Git is 2.54.0, and this repo sets `http.postBuffer` to 524288000, so the HTTP 400 cannot show here. UNKNOWN without a push.
> - S16: `stability.spec` has cases for toast arrival, expiry and the fifth toast. No case covers a toast that grows in place. The other items need the store or a render: UNKNOWN.
>
> **Deviations**
> - For d060, the close condition is UNKNOWN. The mirror has refreshed daily since 10-21, after the recorder fix, but I did not read the bundle for the pullable walk plan.
> - The report missed three things. box-map also says "side by side" in its intro and in the drag paragraph. `Revenue.holdingsSegments` still scales from low to high (the holdings line, not the sales bars). d025 is a question but sits in section 2.
>
> **Next**
> - Correct the report: move Rank 33 to section 3 and the window overlap to section 2. List d008 in one section only. Apply the PARTLY wording above.
