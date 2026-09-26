# The owner's first real TCGplayer test

The owner said YES to both steps, 2026-09-24, and ruled that both run AFTER the overhaul reaches main. Nothing here runs without the owner present. Written by the adversarial reviewer of the send press, round 7, and still current after rounds 8 and 9.

**The owner's test, step by step (after the overhaul reaches main)**
> 0. **Before either step.**
>    - Confirm that main holds the merge and that the primary checkout has synced to it.
>    - Confirm that the live server at :8000 runs the new code: `GET /pipeline/sends` answers 200 on the new code and 404 on the old. You or the orchestrator run this, not a reviewer.
>    - The first open migrates the store to add the `send_claims` table.
>    - After the merge, the app reads from TCGplayer by itself. It fetches the catalogue export when a run waits for a match. It runs the live check when a receipt is due. Each is a read, and no money moves.
> 1. **Staged and roll back.** No press is built for this. Use one call by hand from the primary checkout's venv, with the real cookie from `.env`, on your word:
>    - `tcg_import.push_to_staged(rows_from_csv(<one row, Add to Quantity 1>), listing=True)`. At TCGplayer this calls `initializeexportcsv`, `uploadexportcsv` and `finalizeexportcsv`. Nothing goes live.
>    - Look at the row in the portal's Staged list.
>    - `tcg_import.rollback(upload_id)` calls `rollbackexportcsv`.
>    - **Proof** is only by eye: the upload is gone from the Staged list, and the live export shows that card's quantity unchanged. If the row stays, clear it in the portal and stop, because the rollback then leaves uploads in Staged.
>    - Do not use the mark-down door for this step. Its apply stores an answer. A later listing row of the same card would then move live copies to that price.
> 2. **One real "Send 1 copy".**
>    - Open `#/pricing` at :8000 in a fresh page load.
>    - Pick one run that holds one ready copy of a card TCGplayer holds none of. With nothing live, there is no price row and no move.
>    - Type the price for that row only, and let it save.
>    - The button must read exactly "Send 1 copy to TCGplayer". If it names a price change or a live copy that moves, stop.
>    - Press. The server does these steps in order:
>      - It reads Export From Live.
>      - It runs `reconcile --live --write`.
>      - It runs `emit`, which counts 1 copy and claims it.
>      - It pushes the file to Staged, then runs `movetolive` scoped to this upload.
>    - Read `inventory/sends/<stamp>/send.json`. Expect copies 1, prices 0 and moves `[]`.
>    - About 17 minutes later, the open page runs the live check. Expect "1 of 1 found".
>    - Nothing rolls back a publish (D100). An undo is a quantity change by hand in the portal.
>
>
