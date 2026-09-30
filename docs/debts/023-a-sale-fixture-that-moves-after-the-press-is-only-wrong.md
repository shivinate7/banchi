## 23 — A sale fixture that moves after the press is only wrong sometimes, so no check can flag it

A case in `app/tests/inventory.spec.ts` that mutates its store on the line after a press races the browser. `click()` resolves on dispatch, and `Inventory.tsx:doSell` awaits the sale, adds the copy to `sold`, then bumps `reloads`. When the re-read is served first, the stub answers with the card still on hand and nothing reads again, so the assertion retries a stable wrong answer until it times out. It failed on CI four runs in five and passed on a Mac every time.

The shape does not say whether a case is wrong. Some cases read state the server recomputes, and they are wrong. Others assert on the optimistic overlay (the receipt, the row's `Undo`, the state pill) and are correct with a stale re-read, because their subject is the overlay. A check flagging every post-click mutation flags those. Freezing the fixture through `movesOnSale` weakens them, because the server would then agree with the overlay.

**Outcome at risk.** A new sale case passes on a fast machine and fails on the runner.

**Closes when.** A case declares the property it requires ("this case needs the re-read to disagree with the overlay"), not a flag. A check then flags a post-click mutation in any case that did not declare it. Until then `sellableStore()`'s comment and `movesOnSale` carry the rule. A probe finds it: `await page.waitForTimeout(300)` between a click and its mutation turns the latent race into a deterministic red, and is never committed.
