# Undo in Banchi

Built. Code comments cite the section numbers and the `UN-<n>` ids below, so they do not change.

Undo has two mechanisms and no clock. A mis-press is undone in the second with `U`. A mistake
found later is undone from the card's own record. An undo lasts until the next step is built on
it. After that, the fix is an ordinary action. A toast fades on a timer, and the undo does not
fade with it.

## 1. The model

| path | the writes it covers | how long | where it is reached |
|---|---|---|---|
| the fast path | the newest write on a screen | until built on | `U`, the receipt, and the screen's Undo |
| the slow path | the sale, the retirement, the move | until built on | the card's own row on `#/inventory` |
| the record's control | the hand-fill, the stand-down | for the life of the line | the line's own row |

No server anywhere enforces a time limit. `undo_too_late` is a state test and not a clock. Every
reversal decides "built on" by a fact in the store, and the server refuses with a sentence. The
screen never guesses it. `store/orders.py`'s `reopen_line` has no window and no clock. How long
an undo stays offered is the screen's business, and no screen offers a fixed window. The
receipt has no window. `UNDO_WINDOW_MS` is only the toast's own TTL (`Inventory.tsx`, `Orders.tsx`).

## 2. Two mechanisms, and they are not the same mechanism

- A mis-press, caught in the second: "the way back for an accidental mistake in that second is
  just hitting U."
- A mistake found later: a control on a collapsed row on `#/inventory` that resurrects the card
  exactly where it was.

Neither is a clock. The fast path is short because a receipt is short. The slow path is open for
as long as the store says the card is reversible.

## 3. The fast path: the receipt, and `U`

`U` is the one key for the newest reversible write on a screen, wherever one stands. Undo then
means one thing in the product. `kit/undo.ts`'s `useUndoHotkey` is the one primitive that arms it.
`make kit-adoption` fails a screen that binds `U` itself. Pricing's price field keeps a
field-scoped `U` for typing, and that exception is listed in `scripts/kit-adoption-allow.json`.

Rank decides the fast path and never which rows draw a control. `U` and a toast's own Undo reach
only the newest reversible write. Every sold row keeps its own Undo until that write is built on.
This holds on Inventory and on Cards to pull. Fulfillment's "Pulled today" list works the same
way.

The walk is short and a wrong pull is noticed at once. So the fast path undoes the newest pull.
Anything older is the slow path's job.

## 4. The slow path: the way back is the card

The way back lives on the departed row on `#/inventory`. It does not live on the order's own
line, because pairing orders with undo bottlenecks both. With the fold open, sold and retired
cards sink under the live ones, at the foot of the drawer.

**What it covers.**

- Sold is one state. A pull marks the card sold. There is no second state called pulled.
- The retirement's reversal takes `{"undo": true}` on the retire route. `_state_before_retirement`
  computes what it goes back to.
- A move is undoable while it is the newest write in either box (UN-14).

**What it writes.** It resurrects the card at its own index, and nothing renumbers. The stored
index never moves (D58). A departure is a gap, and the returning card closes it. D10's permanence
rule is about renumbering and index reuse, and neither happens here.

It reverses the order ledger in the same write, where the ledger holds the copy. Otherwise the card could be back on the shelf while the line still counts it fulfilled. The order would then claim a shipment that did not happen, and the card would go to the next buyer.

## 5. The order record keeps the fact and drops the position

"If I were to look at this fulfilled order in the past, it does not need to remain connected to
inventory and positions, it should just be the details like 1 calm rune was pulled."

During the walk, positions are real. Pick a copy, mark it sold, and that specific indexed card is
sold. `U` brings that one back. Afterwards, a past order says what left and not where it was. Its
line reads the card and the count. It draws no drawer, no index and no way back. This is D212
(every copy is fungible and no order claims one) arriving one screen later. `OrderLineProgress`
no longer joins a position per copy at read time.

## 6. The capture strip has per-card granularity

`POST /inventory/<box>/<index>/remove` deletes one capture mid-box and slides every higher card
down one index (D10 ruling 1, the one sanctioned renumber). It takes the target's own capture id
as an aim check. It refuses `renumber_blocked` if any higher card in the drawer has sold, retired
or picked up a listing hold. `app/src/server.ts`'s `removeCardInPlace` is the client half. The
capture strip's rows carry the same press that `BoxBrowse.tsx`'s `CardOps` has. The slide is
wanted, because the cards are still in the hand.

`U` still undoes the newest capture. The strip lists the whole sitting, newest first, across
drawers, in the order the hand took them (D164). The granular press sits beside it.

## 7. What this does not do

- It adds no clock and removes no capability. It changes where each reversal can be reached from.
- It does not put a control on the Fulfiller's screen. His newest sale keeps its Undo until a newer
  sale or the next step builds on it. The slow path is owner work, and the shell-less screen has
  no route to it (D5, D31).
- It does not make `#/inventory` a general writer of the order ledger. One write reverses one pull
  because the two halves are one act.

## 8. Checks that hold

- Three widths, both themes.
- The sale undo's ledger half is mutation-tested against the divergence it closes. Pull a copy,
  reverse it from the card, and assert that the line no longer counts it.
- The resurrect renumbers nothing. The index the card comes back to is the index it left from.
- `renumber_blocked` reaches the capture strip as a sentence that names the blocking card.
- The copy ceiling is measured and reported either way (D284).
- `U`'s binding is in `SHORTCUTS`.
- `check_undo_until_built_on` in T7 proves each server half of §11.

## 9. What would reopen this

A second operator. Every ruling here assumes one hand. The fast path is one hand's own newest press. The slow path assumes that the card in front of you is the card you are reversing. Two people pulling from the same drawers changes what a resurrect means to the other person.

## 10. The order walk's own row: a rank, never a clock

`app/src/OrdersWalkPane.tsx` offers `Undo` in the walk's own row, but only on the newest pull
this walk made. "Newest" is a position and not a countdown. A pull is newest until a later pull
replaces it. Undoing the newest pull hands the rank back to the pull before it, if one still
stands. Only one row ever carries `Undo`, so a walk never piles up open buttons. An older sold copy
is a dead end in this row on purpose. Its way back is the card on `#/inventory` (§4). A test
proves that `Undo` on the newest pull survives after the old window would have closed it. It fakes
the clock and only advances it.

## 11. The undo rules

The owner's rulings:

```
How long: "Anytime, from a history".
A press that cannot be undone: "Never ask".
On expiry: "Yes, until it's built on (Recommended)".
What hurts: "capture mistakes 50%, marking the wrong card sold 30%, wrong review answer 20%".
```

### 11.1 The one undo model

An undo has no clock. It lasts until the next step depends on the action. That step is "built
on". After it, the fix is an ordinary action.

- A clock limits nothing. A toast fades, and the undo does not.
- Rank decides the fast path and never which rows draw a control.
- "Built on" limits both paths.
- "Never ask" holds everywhere but one press. No other press gets a confirm. A press that cannot
  be undone gets an undo instead. The one exception is "undo just N" on the capture strip (Q2). It
  keeps its confirm and stays permanent.

| Action | Built on when | The fix after that |
|---|---|---|
| Capture | Its sitting ends, or a run identifies it. A sitting ends at a 30-minute gap (`SITTING_GAP_MINUTES`, D121, D164). "Undo just N" is permanent and asks first (Q2). | Manage box removes the card (D10 ruling 1). |
| Sale on Inventory | Its photograph is reclaimed (D89), or its box is buried (D134). | "This card is still here" puts the card back. A shipped order re-points (§11.8). |
| Sale on Orders | Its order ships or closes (`store/orders.py`'s `is_terminal_status`), or as for Inventory. | The same "still here" press. The order keeps its count, and its line becomes a hand-fill (§11.8). |
| Sale on Cards to pull | The same as Orders. The Fulfiller keeps the fast path only (D5, D31). | The owner's press on Inventory. |
| Retire | Its box is buried (D134). | None needed. Nothing downstream reads a retirement. |
| Move | Either box changes: a capture, a sale, a retire or a move in either box. | A new move. |
| Review answer | Its SKU is in a written listing file, or holds a listing hold (`undo_too_late`). | The card's own correction route (D252). |
| Review close, stand-down | The card is identified by another route. | The next run asks again. |
| Review close, retire | As for Retire. | As for Retire. |
| Typed price | The next send carries it. | Type the price again and send. |
| Clear typed | The next send carries any cleared SKU. A SKU typed since is kept. | Type the prices again. |
| Hold | Never. A hold withholds, and nothing reads past it. | Release puts back the answer the hold replaced, value and channel, kept in the hold's `before` field. A hold with no earlier answer releases to none. A release, and `U` on a hold, keep the answer's first date. `corpus.stamp_answers` does not re-date a price that returns from a hold. The server sets the hold's kept date from the stored answer it replaces and never takes it from the client. |
| Cut-off change | The next send prices by it. | Set the cut-off again. |
| Divider | A card is captured into its section. A divider `S` put after a middle section is taken out by its key (D300). | Manage box edits the sections (`Inventory.set_sections`). |

### 11.2 What the store guarantees

- `scripts/demo-seed.py` writes the state lines a real card's life writes (UN-4). Without an
  earlier state line, `_state_before_sale` and `_state_before_retirement` refuse to guess, and
  every undo on the demo would refuse.
- `do_retire` touches no queue entry. Every open-entry read skips a departed card
  (`Queue.owed_entries`, UN-8). A card retired from Review therefore stays out of Review, and the
  retire undo brings it back with no second write.

### 11.3 The rules, by id

Capture is 50% of the pain, a wrong sale 30%, a wrong Review answer 20%. "Q" names the owner
question in §11.7 that answered the item.

| id | Behavior | Mechanism | Files | The check that proves it | Q |
|---|---|---|---|---|---|
| UN-1 | The capture strip lists the whole sitting, newest first, in a scrolling strip. | Fast | `app/src/CaptureScreen.tsx`, its CSS, `app/tests/capture-undo.spec.ts` | A 36-shot case reaches capture 24 both ways. | Q1 |
| UN-2 | A reload does not end the sitting. The store rebuilds it by the 30-minute gap. | Fast | `server/capture_server.py` (`GET /capture/sitting`), `app/src/server.ts`, `app/src/types.ts`, `CaptureScreen.tsx` | Capture, reload, and the strip still lists the sitting. | no |
| UN-3 | "Remove just this card?" keeps its confirm. Its words say the removal is permanent and deletes the photo. | Confirm | `app/src/CaptureScreen.tsx`, `app/tests/capture-undo.spec.ts` | The dialog's text names both facts. | Q2 |
| UN-4 | The demo seed logs the state lines a real capture, answer and sale log. | Both | `scripts/demo-seed.py`, a demo self-test | Every seeded card has an origin. | no |
| UN-5 | The newest sale keeps Undo in its row and on the page. Rank replaces the clock. | Fast | `app/src/Inventory.tsx`, `Orders.tsx`, `Fulfillment.tsx`, their specs | Undo still works after a faked 60 s. A newer sale moves it. | Q1 |
| UN-6 | A sold copy keeps its place, and its control becomes Undo (D57). The walk never advances itself. | Fast | `app/src/OrdersWalkPane.tsx`, `Fulfillment.tsx`, their specs | A rect-diff after a pull: no other row moves (D118). | no |
| UN-7 | A sale refuses its undo once built on. "This card is still here" puts the card back. A shipped order's line re-points to a hand-fill (§11.8). | Slow | `server/capture_server.py`, `store/orders.py`, `app/src/BoxBrowse.tsx`, `server.ts` | Ship an order, then undo: a refusal. "Still here" restores the card, and the order keeps its count. | no |
| UN-8 | A departed card owes no answer. Open-entry reads skip it. | Both | `server/capture_server.py`, `app/src/ReviewQueue.tsx` (copy) | Retire from Review, then reload. The card is gone, and undo brings it back. | no |
| UN-9 | On a phone the Review receipt is in view, and its arrow meets the 40 px floor (D117). | Fast | `app/src/ReviewQueue.tsx`, its spec | At 390, Undo is in view and 40 px or more. | no |
| UN-10 | One kit hook arms `U`. | Fast | `app/src/kit/undo.ts`, `App.tsx` `SHORTCUTS`, `Gallery.tsx` | One spec presses `U` on each screen. `make kit-adoption` fails a screen that binds `U` itself. | no |
| UN-11 | The server keeps every "Clear typed" not yet restored, until a send builds on it. Each Undo names its own clear. The Restore notice lists every one, newest first, and folds past three. | Both | `server/pipeline_routes.py`, `pipeline/corpus.py`, `Pricing.tsx`, `ClearPrices.tsx` | Clear, reload, and restore. A send in between refuses it. | no |
| UN-12 | A Pricing hold answers `U`, and one `U` undoes a whole hold. | Fast | `app/src/Pricing.tsx`, its spec | Hold a no-market SKU, press `U` once. The hold is fully gone. | no |
| UN-13 | A cut-off change has a receipt and a stack entry that holds the prior value. | Fast | `app/src/Pricing.tsx`, its spec | Change it, press `U`, and the old value is back. | no |
| UN-14 | A move is undone by deleting the transplant while it is the newest, and restoring the tombstone. | Both | `store/master.py`, `server/capture_server.py`, `Inventory.tsx` | Move, then undo. The card is back at its index, and nothing else moves. | Q1 |
| UN-15 | While no card is behind a divider, `U` drops it through `DELETE /boxes/<box>/sections?div=<key>`. | Fast | `CaptureScreen.tsx`, `closeSection`, `Inventory.close_section` | Press `S`, then `U`. The sections are as before. | no |

`Inventory.tsx`'s Move-to-box receipt carries Undo (`undoMove`). It survives until the move is
built on (`move_built_on`). `BoxOps.tsx`'s batched move (cards picked in its sheet or the whole box, D83)
has no undo.

### 11.7 The owner's rulings

**Q1. Change the clock sentences in D164, D28, D57, §4 and §7 to "until it is built on"?** The
answer was "Switch all five (Recommended)". D164, D28 and D57 each carry the amendment. UN-14 is
in.

**Q2. How does "undo just 24" work with no confirm?** The answer was "Keep the confirm here
only". "Undo just N" keeps its confirm and stays permanent. It is the one exception to "Never
ask".

### 11.8 The store halves

T7's `check_undo_until_built_on` proves each one.

- **UN-7, "This card is still here", on a shipped order.** It is `{"still_here": true}` on the
  sold route. The card goes back. The order keeps its count (D212), and the card's capture id comes
  off the line as a `sold_separately` hand-fill. With the id left on the line, a later pull of the
  same card would refuse as a second shipment. On an open order, "still here" releases the line, as
  a plain undo does (§4). The owner's ruling: "Card back, order re-points". The SKU's `sold_here`
  falls by one.
- **UN-2, the server decides when the sitting ended.** `GET /capture/sitting` answers `open: false`
  and no cards once the newest capture is more than 30 minutes old. The capture undo route reads
  the same rule and refuses `capture_built_on` for a card outside the open sitting. The fix after
  that is Manage box. `SITTING_GAP_MINUTES` copies `app/src/storeHistory.ts`'s `GAP_MINUTES`. T7
  reads the TypeScript constant and fails when they differ.
- **UN-14.** A transplant carries `moved_from`. The sitting read leaves out tombstones and
  transplants. The capture undo refuses a transplant with `capture_built_on`, so it cannot delete a
  moved card or its photo. A tombstone's name is `moved:<name>@<its key>`, so a card moved back or
  on to a third box leaves distinct tombstones and the UNIQUE index holds. The card's own name is
  unchanged (D172). The move undo reads the older bare form too. A divider put in behind the
  transplant builds on the move. A batch move is undone one card at a time, and only its last card
  is the newest.
- **A chain of moves undoes one link.** Move a card from A to B, then from B to C. Undo the second
  move, and the card is back at B. The first move is then built on, because box B changed. Its fix
  is an ordinary move back to A.
- **The move undo restores the order key too (D294).** The card comes home at its own index and at
  its own place in the walk. A section reorder inside a box does not build on a move, because it
  writes no card history.

### 11.9 The capture screen

- **UN-1.** `CaptureScreen.tsx`'s `undoStack` is the whole sitting. `.capture-undo-list` scrolls
  inside its own footer with a fixed `max-height` at desktop. The tablet breakpoint keeps its own
  horizontal scroll. Neither grows the page.
- **UN-15.** `doSection` remembers the box it opened the divider in (`pendingDivider`). `U` takes
  that divider back out through `closeSection`, with the key that `S`'s answer gave it. The store
  removes only that divider, while it is the last and empty. It refuses a stale `U` as
  `divider_built_on`. A refusal clears `pendingDivider`, so the next `U` reaches the captures.
  The route removes a divider by key and not by `updateBox({ sections })`. That route reads card
  counts, and the box's `sections` are order keys, so other dividers moved (D294). `U` fires only
  while `pendingDivider` is the newer of the two reversible writes, by `at` against the sitting's
  newest shot. A capture into the same box clears it, because the divider is built on.
- **UN-3.** `do_remove_card` still consumes the photograph and slides the later cards down, with no
  undo. The dialog says "This permanently deletes the record and its photograph".
- **UN-2, screen half.** `getCaptureSitting()` runs once. It waits for the game registry, which is
  the one thing that can resolve a hydrated card's `game` key into a `GameEntry`. A second read
  would duplicate every row `shots` already holds. `undoNote` reads `capture_built_on` as it reads
  every other refusal: the server's own sentence and code, verbatim. It also offers a "Manage box"
  button, named for the refused card's own box.

### 11.10 The sale, Review and Pricing screens

- **UN-5.** `Inventory.tsx`, `Orders.tsx` and `Fulfillment.tsx` keep a receipt list ranked by
  recency and never pruned by a clock. `remember` prepends and dedupes by key.
- **UN-6.** `OrdersWalkPane.tsx` does not advance itself. The sold copy's own `RowAction` reads
  `receipts` fresh every render and turns into `Undo` in the row it was pressed from. Nothing else
  on the pane re-mounts, so no other row's button can land under a repeated tap. The operator moves
  on with `J` or `K`, or a row in the walk list. `OrderDetail` always renders `PickLine` with
  `hidePicks`, so `PickLine` never draws a takeable copy's Mark sold. A fix there would be
  unreachable. Fulfillment's row-per-card list never removed a copy the way Orders did. Its defect
  was the `.ff-sheet`, and it needed no row freeze.
- **UN-9, UN-10.** `kit/undo.ts`'s `useUndoHotkey` is the one `U` primitive. `kit/index.tsx`'s
  `PageUndo` is a header door. Review does not draw it (§11.12). `Page` has no `undo` prop.
  `Gallery.tsx`'s specimen draws `PageUndo` and its `.bn-page-undo` wrapper directly. A screen that
  wants the header door writes that same pair.
- **UN-12.** `Pricing.tsx`'s `Undo` type is `{ id } & ({ kind: 'answer', writes } | { kind: 'cutoff', before })`.
  Each `writes` item holds a SKU, its prior answer and its channel. `setHold` pushes both fields it
  touches as one `answer` entry.
- **UN-13.** The store-wide cut-off (`setCut`) has a receipt and a `{ kind: 'cutoff', before }` entry
  that holds the prior `threshold` and `sub_threshold`. It reverts on the same pop other entries do.
- **UN-7, screen half.** `BoxBrowse.tsx`'s `CardOps` offers "This card is still here"
  (`saleStillHere`) once the ordinary reversal refuses `sale_built_on`. It is never a retry of the
  same request. The card is back in stock, and the order line it was pulled for is marked filled by
  hand.
- **UN-14, screen half.** `Inventory.tsx`'s `Receipt.kind` includes `'move'`. `doMove` folds a move
  into the same `remember` and `receipts` list a sale or retirement uses. `U` and the toast's own
  Undo reach it, ranked the same way. `Receipt` keeps the transplant's current box, index and
  capture id. On `move_built_on`, an ordinary `moveCard` aims at that current position and goes back
  to the receipt's own origin box. It is never a second route the way UN-7's `saleStillHere` is.
- **UN-11, screen half.** `Pricing.tsx` reads `GET /pricing`'s `last_clear` and offers "Restore N
  cleared" once the toast that named the clear is gone. `restoreLastClear`'s own answer carries no
  per-SKU values. So the screen reads the corpus fresh afterward and takes each restored SKU's
  answer off that read.

### 11.11 One vocabulary

Every write that an Undo press or a toast's own Undo reaches reads `"<what it undid> undone"`. This holds whether it is a provable reversal or a different write with the same visible effect. A refusal stays its own plain sentence. It is a reason to give and not an outcome to name. Never borrow "undone" for it.

- Sale, retirement, move, hold and cut-off read "Sale undone", "Retirement undone" and "Move
  undone".
- `BoxBrowse.tsx`'s `CardOps.resurrect` reads "Sale undone" or "Retirement undone".
- `CardOps.stillHere` (UN-7's `saleStillHere`, a different write reached only after an ordinary
  reversal refuses `sale_built_on`) reads "Card undone".
- Orders' pull undo reads "Pull undone". Its `pull_not_recorded` case, where the pull was already
  reversed elsewhere, reads "Already undone".
- Pricing's restore reads "N prices undone".
- Refusals read plainly: "Not undone" and "The card was not put back". The reason goes in the body,
  never the raw code.

### 11.12 Review draws no header undo

`.review-tray`'s own row, in the body, reserves its height and moves nothing when the receipt
mounts. A second, unreserved receipt in the page header pushed `.review-filters` and everything
below it down 56px on the first answer of a session. Reserving that header row would cost
`#/review`'s no-scrolling floor 54px it has no slack for. So `ReviewQueue.tsx` draws only the
in-body Tray. The Tray sits inside `.review-body`, on screen with the card at every width the
product ships. That keeps D118 and the no-scrolling floor intact together.

An overlay `.bn-page-undo` never moves layout, so a screen that needs both a header door and zero
reserved space can build one from `PageUndo`.
