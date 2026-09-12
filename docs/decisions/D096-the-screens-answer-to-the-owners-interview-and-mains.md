## D96 — The screens answer to the owner's interview, and main's history is not the authority

**Main advanced 19 commits while this branch was open, and the owner was walked through every difference and ruled on each one.** Two sittings, 2026-09-03. The instruction that governs the whole exercise is theirs, verbatim: *"You will literally be breaking a bunch of stuff likely that was made and made stale on main. Your whole goal will be to make sure the new rules answer to what was built here, not you conforming to it."* This entry exists so that a later session reading main's history does not read a deviation as a regression and quietly restore it.

### What was kept against main, and why

**The order walk stays per copy on `#/orders`.** The owner: *"I for sure need the ability to see where every copy of the ordered card lies and I get to control picking which copy I reach for. I don't want the walk picking for me"*, and of the alternative, *"main's was haphazardly done"*. D90's envelope walk — the order taking over `#/inventory`, the arrows stepping the queue, and one press recording the whole envelope — is not adopted here. **This does not repeal D90's argument**, which is about the operator's own error point and is sound; it is the owner choosing a different shape after using both, and the per-copy walk with its per-copy undo is what they use. The rebuilt screen answers the same want one register up, in D97.

**The consequence is named rather than discovered.** `POST /orders/fill` and `POST /orders/fill/undo` arrive with the merge and are reachable from no screen on this branch. By `CLAUDE.md`'s route-is-not-a-feature rule that is two server-only capabilities, which the rule says are not done — recorded here as a debt taken on the owner's instruction, not as a thing that landed. They are deleted, or they get the screen D90 built for them, and the decision is the owner's; nothing else should be built on them meanwhile.

**The order fetch stays one press.** D91 made it two: a status preview, then the fetch. The owner ruled against the preview step and kept the single press, with the receipt carrying what the fetch checked, took and left.

**The card-number sigil sweep is deferred wholesale.** D92 rules that a bare `#` is a count and a key carries a sigil, and this branch's labels were not swept to it. Every label stays as the rebuild drew it, including the capture undo rows, where the owner was shown the ambiguity against real data — box 2, section 2, card 3 is slot 86, and the row draws a bare number — and chose to leave it. The sweep is a later pass, and D92 is not weakened by its absence here: nothing on this branch contradicts it, the labels simply have not been brought to it yet.

### What was adopted from main, screen half and all

Three of main's rulings retired something the pipeline could no longer say, and each needed a screen to stop asking about it. All three landed here.

**D3's amendment retired the finish cross-check**, so the review queue's *"Which finish is this?"* question over `metadata_detection_disagreement` is deleted, at four sites plus `reasons.ts`. The code survives in `RETIRED_REASON_LABELS`, so an entry queued under it still renders a name instead of a raw string; the other three finish reasons are untouched and still ask. **D64 and D65's amendment retired the export delta guard**, so both "Fetch anyway" buttons, the finish-claim bypass checkbox and the verified/unverified sentence are gone, replaced by a plain post-fetch receipt — rows, game, scope, and the previous export it can name — that reassures and refuses nothing.

**D59's amendment dated every reading of `live`, and this branch draws the date.** A `live` count is now written with the age of the reading beside it, on `#/inventory`'s locations, on a box's browse rows and on a box's release plan. A live number with no age reads as a fact about the marketplace when it is a fact about the last time this store looked, and those are different claims about a figure that decides a cap. Where a panel shows several readings at once the oldest is drawn as a bound — *read within 3 hours* — because a mid-dot list of stamps invites arithmetic nobody wants to do.

### What the owner ruled stays exactly as the rebuild made it

Each is a place where main or an earlier rule says otherwise, so a later session would "fix" it. Owner screens show human labels, not raw enum strings; the machine value stays on hover and in the run log. Receipts expire as toasts rather than filling a panel. Disclosures start collapsed, the Runs scope options included, and those can hold a refusal. The review header shows the card count, with reason chips only where there is a choice. A box has one position track until it has dividers. Pricing says nothing about import filenames, which is the single-file emit default read forward.

### What would reopen this

**A second operator, or the owner using the envelope walk somewhere else.** The per-copy ruling is a measurement of one person's hands at one set of drawers. And an accumulating count of orders pulled with no record of which copies went — the doubt D90 exists to end — would say the envelope press was right and this screen has to grow one.

### Amended 2026-09-04 — the debt is discharged by deletion, and the one non-duplicate idea was kept

**The two answers this entry left open were `deleted` and `they get the screen D90 built for them`, and the answer is deleted.** 1,484 lines: `app/src/orderWalk.ts`, `OrderWalkBanner.tsx` and `OrderWalkBanner.css` whole (1,000 of them), `fillEnvelope`/`undoEnvelope` and the `fill()` helper behind both in `server.ts`, `FillLine`/`FillResult` in `types.ts`, `do_order_fill` with its dispatcher line and its two constants in `server/capture_server.py`, and harness T7's `check_order_fill`. Nothing referenced any of it: the five greps came back with hits only inside the set being deleted, and `make harness` passes nine of nine without the check that covered the route.

**Nothing was ported, because the one capability that sounded distinct had already been rebuilt here.** D90's wave mode — the cross-order pass that walks the drawers in box order rather than in the order the carts were composed — is `Orders.tsx`'s `buildWalk`/`WalkView`, the "Walk the boxes" mode, written independently on this branch before anyone compared the two. It does the same sort over the same landing, and it does it while keeping the copy the operator reaches for theirs to choose (D93, D97), which is the ruling above. The deletion cost this product no behavior.

**What was NOT deleted is the pair of helpers, and the reason is in the code.** `_prepare_targets` and `_ledger_pull` were lifted out of `do_order_pull` for the envelope's sake and are still `POST /orders/pull`'s own two phases; both docstrings now say the second door is gone rather than naming a route that answers 404. A refactor folding them back inline is a separate change with its own argument, and this was not it.

**One idea of D90's was kept and it is a figure, not a press.** The walk's head counts CARDS; the unit you pack is an ENVELOPE. So it also says how many orders are whole — *"3 of 5 orders fully pulled"*, over `done` against `open + done`.

**The derivation that reads right is the one that cannot work, and it was written first.** Counted over `open`, a finished order is zero by construction: `open` is the ledger's answer to *does this still owe copies*, so an order leaves it the instant its last copy is pulled. Measured by pulling the one copy of order A47CCC-13B33 through the screen: the page header moved from *20 open orders* to *19 open orders and 1 done*, and the pill stayed absent. The pull was reversed after. A typecheck could not have said any of it; the browser did.

**It is a count and not D90's per-order list**, which is what the reopening condition above asks for: no record of which copies went, and no second pick list beside the one on screen. The denominator did not survive — see below.

---

### Amended 2026-09-04 — the walk's figure is a count over the pass, and the denominator is deleted rather than fixed

**The figure above is kept and its denominator is not.** *"3 of 5 orders fully pulled"* becomes *"3 orders complete in this pass"*. It is still counted over `done` and not over `open`, for the reason the amendment above already argues in full, and that half is untouched.

**What is deleted is the pair, and the entry's own words for it are what fail.** The denominator was *"the pair that header already prints from the same two arrays — so the walk's figure and the page's headline cannot disagree"*, and `done` there is every order the ledger has ever completed, with no window and nothing pruned. The agreement was real; the figure was not. A store with 200 completed orders and 3 open drew **`200 of 203` on a three-order walk** — a lifetime statistic wearing a progress figure's clothes, correct on the day it was measured at 20 open and 0 done and wrong on every day after that has a sale in it.

**Freezing the denominator to the pass was tried first, and it buys a worse state than it sells.** Orders arrive while you walk, and this screen re-reads after every pull. So a pass over two orders with both pulled draws `2 of 2` beside a head reading `3 still to pull across 1 open order`. **A fraction that has reached its own denominator says FINISHED**, over a screen with work on it, and no wording rescues it. A count cannot make that claim, because it never had a total to reach. That is the whole argument for deleting the denominator instead of fixing it.

**`in this pass` is what the frozen set is still for.** `walkKeys` is the orders the walk began over; the count is its members that have left `open`. It starts at 0, where every walk starts, and only rises.

**A toggle is not the end of a pass, and freezing on every entry made it one.** A fresh freeze is drawn from `open`, which an order leaves the instant its last copy is recorded, so it can never contain one the pass has already finished. Measured: after one pull the figure read one, and after `By order` → `Walk the boxes` it was **gone**. The pass is held across the toggle instead, and `onFetch` ends it — orders arriving off TCGplayer are a new sitting, and the only boundary the operator draws.

**`complete` and not `fully pulled`.** An order reaches `done` by routes this screen never sees: a sale on `#/inventory`, an ingest, another device. The old verb claimed presses the figure cannot account for.

**The figure and the headline can now disagree, and on a store with history they will.** That is the right trade: the headline is about the ledger, the pill is about the sitting you are in. A `null` set draws nothing rather than falling back — a silent fallback is how the lifetime figure would come back.

**What would reopen this.** Mid-pass arrivals becoming frequent enough that the operator wants them counted, which is a different figure and not this one. A pass long enough that losing it on a reload is felt, which would put the set in the hash after all — declined here on D90's own reasoning about where order identity lives. And a tab left open past the sitting it describes: `HubState` lives as long as the tab, so `walkKeys` does too, and nothing on screen says the pass is stale. `docs/DEBTS.md` carries that one.

**Observed failing, four mutations.** The ledger's lifetime figure restored: the pill appears **on arrival**, before anything is pulled, which the case forbids. Counted over `open`: no figure ever. The set never frozen: no figure ever. The set refrozen on every entry: the figure survives the pull and vanishes on the round trip through `By order`. **The fixture carries a third order the ledger finished before the walk began** — without it the pass figure and the lifetime figure agree, and the case would have passed against the figure it replaces.
